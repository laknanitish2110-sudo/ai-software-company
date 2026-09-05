import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Set, Callable, Awaitable
from app.services.redis_coordinator import redis_coordinator, LockHeartbeat

logger = logging.getLogger(__name__)

from app.core.database import (
    create_project,
    get_project,
    update_project_status,
    save_agent_output,
    update_output_status,
    get_latest_output,
    set_memory,
    get_memory,
)
from app.agents.engine import run_agent, cross_review, _sanitize_error
from app.services.workflow_search import analyze_for_problem, analyze_by_components
from app.services.file_generator import generate_project_files, get_generated_files_list
from app.services.workflow_generator import generate_workflow_json
from app.services.pptx_generator import generate_pptx
from app.services.docx_generator import generate_docx
from app.services.webhook import send_agent_event, send_research_data, send_approval_event, send_deliverables_ready
from app.models.schemas import (
    AgentRole,
    ProjectStatus,
    PIPELINE_ORDER,
    WORKING_STAGES,
    REVIEW_STAGES,
)
from app.models.execution_schema import validate_and_detect_execution_plan, parse_or_convert_dod
from app.services.sandbox_runner import run_sandbox_execution
from app.agents.qa import evaluate_qa_results
from app.services.repair_context_builder import build_repair_context
from app.agents.fixer import generate_targeted_patch
from app.services.patch_applier import PatchApplier
from app.services.regression_checker import capture_baseline, compare_execution_baseline
from app.services.repair_loop import RepairLoopService
from app.services.security_gate import scan_files as security_scan_files


WSCallback = Callable[[str, str, dict], Awaitable[None]]


class Orchestrator:
    def __init__(self):
        self._ws_callback: WSCallback | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._active_executions: set[str] = set()

    def set_ws_callback(self, callback: WSCallback):
        self._ws_callback = callback

    async def _notify(self, msg_type: str, project_id: str, data: dict):
        if self._ws_callback:
            await self._ws_callback(msg_type, project_id, data)
        try:
            await redis_coordinator.publish_event(project_id, msg_type, data)
        except Exception:
            pass

    async def register_project_execution(self, project_id: str) -> str:
        token = await redis_coordinator.acquire_lock(project_id, ttl_seconds=180)
        if not token:
            raise ValueError(f"PROJECT_EXECUTION_IN_PROGRESS: Execution is already running for project {project_id}.")
        return token

    async def start_project(self, problem_statement: str, user_id: str = "legacy_owner", auto_approve: bool = False, execution_id: Optional[str] = None, route: str = "full") -> dict:
        from app.services.task_router import get_route_agents, PIPELINE_ROUTES
        if route not in PIPELINE_ROUTES:
            route = "full"

        project = await create_project(problem_statement, user_id=user_id)
        project_id = project["id"]

        await set_memory(project_id, "problem_statement", problem_statement, "founder")
        await set_memory(project_id, "pipeline_route", route, "system")

        if auto_approve:
            await set_memory(project_id, "auto_approve", "true", "founder")

        if execution_id:
            await set_memory(project_id, "active_execution_id", execution_id, "system")

        lock_token = await self.register_project_execution(project_id)

        route_agents = get_route_agents(route)
        first_post_ceo = AgentRole(route_agents[1])

        async def _run_pipeline():
            token = lock_token
            heartbeat = None
            try:
                if execution_id and await redis_coordinator.is_cancelled(execution_id):
                    from app.services.task_queue import ExecutionCancelledError
                    raise ExecutionCancelledError(f"Cancellation requested for execution {execution_id}")

                heartbeat = LockHeartbeat(project_id, token, ttl_seconds=60, interval_seconds=15)
                heartbeat.start()

                await self._notify("route_selected", project_id, {
                    "route": route,
                    "agents": route_agents,
                    "message": f"Pipeline route: {PIPELINE_ROUTES[route]['name']} ({len(route_agents)} agents)"
                })

                # Step 0: Query domain memory for relevant past learnings
                try:
                    from app.services.domain_memory import get_relevant_learnings
                    domain_context = await get_relevant_learnings(problem_statement, project_id=project_id)
                    if domain_context:
                        await set_memory(project_id, "_domain_learnings", domain_context, "domain_memory")
                        await self._notify("domain_memory", project_id, {
                            "message": "Loaded learnings from past projects to guide this run."
                        })
                except Exception as e:
                    logger.warning(f"Domain memory query failed (non-critical): {e}")

                # Step 1: CEO analyzes problem
                await self._notify("agent_started", project_id, {
                    "role": "ceo",
                    "message": "CEO is analyzing the problem statement..."
                })

                ceo_output = await run_agent(project_id, AgentRole.CEO)
                await update_output_status(ceo_output["id"], "approved")
                await set_memory(project_id, "ceo_brief", str(ceo_output["content"]), "ceo")

                ceo_content = ceo_output.get("content", {})
                deliverable_type = "code"
                components = []
                if isinstance(ceo_content, dict):
                    deliverable_type = ceo_content.get("deliverable_type", "code")
                    components = ceo_content.get("components", [])

                await set_memory(project_id, "deliverable_type", deliverable_type, "ceo")

                await self._notify("agent_completed", project_id, {
                    "role": "ceo",
                    "message": f"CEO classified deliverable as '{deliverable_type}' with {len(components)} components."
                })

                # Step 2: RAG searches PER-COMPONENT using CEO's breakdown
                try:
                    if components:
                        workflow_analysis = analyze_by_components(components, limit_per_component=5)
                    else:
                        workflow_analysis = analyze_for_problem(problem_statement, limit=10)

                    await set_memory(project_id, "workflow_recommendations", json.dumps({
                        "total_matches": workflow_analysis["total_matches"],
                        "keywords": workflow_analysis.get("keywords_extracted", []),
                        "components_searched": workflow_analysis.get("components_searched", []),
                        "component_results": workflow_analysis.get("component_results", {}),
                        "reusable": [{"name": w["name"], "category": w["domain_category"],
                                      "integrations": w.get("integrations", ""), "ai": w.get("has_ai_nodes", False),
                                      "score": w["relevance_score"],
                                      "component": w.get("matched_component", "")}
                                     for w in workflow_analysis.get("reusable", [])[:5]],
                        "modifiable": [{"name": w["name"], "category": w["domain_category"],
                                        "integrations": w.get("integrations", ""), "ai": w.get("has_ai_nodes", False),
                                        "score": w["relevance_score"],
                                        "component": w.get("matched_component", "")}
                                       for w in workflow_analysis.get("modifiable", [])[:5]],
                        "inspiration": [{"name": w["name"], "category": w["domain_category"]}
                                        for w in workflow_analysis.get("inspiration", [])[:3]],
                        "categories_matched": workflow_analysis["categories_matched"],
                        "sih_themes_matched": workflow_analysis["sih_themes_matched"],
                        "summary": workflow_analysis["summary"],
                        "deliverable_type": deliverable_type,
                    }), "rag_agent")
                    await self._notify("workflow_analysis", project_id, {
                        "message": f"RAG searched {len(components)} components across 19,800+ workflows: {workflow_analysis['summary']}",
                        "total_matches": workflow_analysis["total_matches"],
                        "categories": workflow_analysis["categories_matched"],
                        "deliverable_type": deliverable_type,
                    })
                except Exception as e:
                    logger.warning(f"Workflow analysis failed (non-critical): {e}")

                await self._start_next_agent(project_id, first_post_ceo, execution_id=execution_id)
            except Exception as e:
                logger.error(f"Pipeline startup failed: {e}")
                await self._notify("error", project_id, {
                    "role": "ceo",
                    "message": f"Pipeline startup error: {str(e)}"
                })

        asyncio.create_task(_run_pipeline())
        return project

    async def _start_next_agent(self, project_id: str, role: AgentRole, execution_id: Optional[str] = None):
        exec_id = execution_id
        if not exec_id:
            mem = await get_memory(project_id)
            exec_id = mem.get("active_execution_id")

        if exec_id and await redis_coordinator.is_cancelled(exec_id):
            from app.services.task_queue import ExecutionCancelledError
            raise ExecutionCancelledError(f"Cancellation requested for execution {exec_id}")

        working_status = WORKING_STAGES.get(role)
        if working_status:
            await update_project_status(project_id, working_status.value)

        await self._notify("agent_started", project_id, {
            "role": role.value,
            "message": f"{role.value.replace('_', ' ').title()} is now working..."
        })

        async def _run():
            try:
                if exec_id and await redis_coordinator.is_cancelled(exec_id):
                    from app.services.task_queue import ExecutionCancelledError
                    raise ExecutionCancelledError(f"Cancellation requested for execution {exec_id}")

                token_count = 0

                async def _stream_to_ws(token: str):
                    nonlocal token_count
                    token_count += 1
                    if token_count % 3 == 0:
                        await self._notify("agent_stream", project_id, {
                            "role": role.value,
                            "token": token,
                            "token_count": token_count,
                        })

                output = await run_agent(project_id, role, stream_callback=_stream_to_ws)

                review_data = None
                try:
                    review_data = await cross_review(project_id, role, output["content"])
                except Exception:
                    pass

                try:
                    await send_agent_event("agent_completed", project_id, role.value, output.get("content"), review_data)
                except Exception:
                    pass

                if role == AgentRole.ENGINEER and isinstance(output.get("content"), dict):
                    try:
                        if exec_id and await redis_coordinator.is_cancelled(exec_id):
                            from app.services.task_queue import ExecutionCancelledError
                            raise ExecutionCancelledError(f"Cancellation requested for execution {exec_id}")

                        await self._notify("sandbox_started", project_id, {
                            "role": "sandbox",
                            "message": "Executing generated software in isolated Sandbox..."
                        })
                        eng_content = output["content"]
                        plan = validate_and_detect_execution_plan(eng_content)
                        files = eng_content.get("files", [])
                        
                        ba_out = await get_latest_output(project_id, AgentRole.BUSINESS_ANALYST.value)
                        ba_content = ba_out.get("content", {}) if ba_out else {}
                        dod = parse_or_convert_dod(ba_content, plan)

                        arch_out = await get_latest_output(project_id, AgentRole.ARCHITECT.value)
                        arch_content = arch_out.get("content", {}) if arch_out else {}

                        async def notify_bridge(event_type: str, data: dict):
                            await self._notify(event_type, project_id, data)

                        # P2.5 Bounded Self-Repair Loop Delegation (Max 3 attempts)
                        repair_service = RepairLoopService()
                        final_val_res = await repair_service.run_repair_loop(
                            project_id=project_id,
                            files=files,
                            plan=plan,
                            dod=dod,
                            problem_statement=(await get_project(project_id) or {}).get("problem_statement", ""),
                            engineer_output=eng_content,
                            architect_output=arch_content,
                            notify_cb=notify_bridge,
                            execution_id=exec_id
                        )

                        val_json = final_val_res.model_dump_json() if hasattr(final_val_res, "model_dump_json") else json.dumps(final_val_res.dict())
                        await set_memory(project_id, "final_validation_result", val_json, "repair_loop")

                        if final_val_res.final_files:
                            await set_memory(project_id, "repaired_files", json.dumps(final_val_res.final_files), "repair_loop")

                        if final_val_res.build_artifacts:
                            try:
                                from app.services.file_generator import generate_deployable_bundle
                                generate_deployable_bundle(project_id, final_val_res.build_artifacts)
                                await set_memory(project_id, "has_deployable_bundle", "true", "repair_loop")
                            except Exception as bundle_err:
                                logger.warning(f"Deployable bundle creation failed: {bundle_err}")

                        val_data = json.loads(val_json)
                        await self._notify("sandbox_completed", project_id, {
                            "role": "sandbox",
                            "status": final_val_res.final_status,
                            "attempts_used": final_val_res.attempts_used,
                            "message": f"Repair Loop finished ({final_val_res.final_status}) after {final_val_res.attempts_used} attempt(s): {final_val_res.reason}",
                            "validation_result": val_data,
                        })

                        preview_url = val_data.get("final_execution_result", {}).get("preview_url") if val_data.get("final_execution_result") else None
                        if preview_url:
                            await self._notify("sandbox_preview_ready", project_id, {
                                "role": "sandbox",
                                "preview_url": preview_url,
                                "message": "Live preview available!",
                            })
                    except Exception as sbx_err:
                        logger.warning(f"Sandbox/QA repair loop execution failed: {sbx_err}")
                        await self._notify("error", project_id, {
                            "role": "sandbox",
                            "message": f"Sandbox/QA execution error: {str(sbx_err)}"
                        })

                if role == AgentRole.ENGINEER and isinstance(output.get("content"), dict):
                    try:
                        eng_files = output["content"].get("files", [])
                        mem_data = await get_memory(project_id)
                        repaired_json = mem_data.get("repaired_files")
                        if repaired_json:
                            try:
                                repaired = json.loads(repaired_json)
                                if repaired:
                                    eng_files = repaired
                            except Exception:
                                pass
                        if eng_files:
                            scan_result = security_scan_files(eng_files)
                            await set_memory(project_id, "security_scan", json.dumps(scan_result.to_dict()), "security_gate")
                            scan_dict = scan_result.to_dict()
                            scan_dict["role"] = "engineer"
                            scan_dict["message"] = scan_result.summary
                            await self._notify("security_scan", project_id, scan_dict)
                    except Exception as sec_err:
                        logger.warning(f"Security scan failed (non-critical): {sec_err}")

                review_status = REVIEW_STAGES.get(role)
                if review_status:
                    await update_project_status(project_id, review_status.value)

                    if review_data:
                        await self._notify("peer_review_completed", project_id, {
                            "role": role.value,
                            "reviewer": review_data.get("reviewer", ""),
                            "team_note": review_data.get("team_note", ""),
                            "message": f"{review_data.get('reviewer_label', 'A teammate')} reviewed this work: \"{review_data.get('team_note', '')}\""
                        })

                    mem = await get_memory(project_id)
                    if mem.get("auto_approve") == "true":
                        await self._notify("approval_needed", project_id, {
                            "role": role.value,
                            "output_id": output["id"],
                            "content": output["content"],
                            "message": f"{role.value.replace('_', ' ').title()} completed. Auto-approving..."
                        })
                        await asyncio.sleep(1)
                        await self.handle_approval(project_id, output["id"], True, execution_id=exec_id)
                    else:
                        await self._notify("approval_needed", project_id, {
                            "role": role.value,
                            "output_id": output["id"],
                            "content": output["content"],
                            "message": f"{role.value.replace('_', ' ').title()} has completed their work. Please review and approve."
                        })
                elif role == AgentRole.PPT:
                    if isinstance(output["content"], dict):
                        try:
                            pptx_path = generate_pptx(project_id, output["content"])
                            await self._notify("pptx_generated", project_id, {
                                "message": "Presentation (.pptx) generated and ready for download!"
                            })
                        except Exception as e:
                            await self._notify("error", project_id, {
                                "message": f"PPTX generation error: {str(e)}"
                            })
                    try:
                        from app.core.database import get_project_outputs, get_memory as get_mem
                        all_outputs = await get_project_outputs(project_id)
                        all_memory = await get_mem(project_id)
                        proj = await get_project(project_id)
                        docx_path = generate_docx(project_id, proj, all_outputs, all_memory)
                        await self._notify("docx_generated", project_id, {
                            "message": "Project report (.docx) generated and ready for download!"
                        })
                    except Exception as e:
                        await self._notify("error", project_id, {
                            "message": f"DOCX generation error: {str(e)}"
                        })

                    await update_project_status(project_id, ProjectStatus.COMPLETED.value)

                    # Extract domain learnings for future projects
                    try:
                        from app.services.domain_memory import extract_learnings
                        saved_learnings = await extract_learnings(project_id)
                        if saved_learnings:
                            await self._notify("domain_memory", project_id, {
                                "message": f"Extracted {len(saved_learnings)} learnings for future projects."
                            })
                    except Exception as e:
                        logger.warning(f"Domain learning extraction failed (non-critical): {e}")

                    try:
                        await send_agent_event("project_completed", project_id, "all", None, None)
                    except Exception:
                        pass

                    try:
                        proj_data = await get_project(project_id)
                        p_name = "Project"
                        if isinstance(output["content"], dict):
                            rd = output["content"].get("report_data", {})
                            if isinstance(rd, dict):
                                p_name = rd.get("title", p_name)
                        delivs = ["code.zip", "presentation.pptx", "report.docx"]
                        await send_deliverables_ready(project_id, p_name, delivs)
                    except Exception:
                        pass

                    await self._notify("project_completed", project_id, {
                        "role": role.value,
                        "output_id": output["id"],
                        "content": output["content"],
                        "message": "All work is complete! Your project is ready."
                    })
            except Exception as e:
                clean_msg = _sanitize_error(str(e))
                logger.error(f"Uncaught pipeline exception for project {project_id}: {clean_msg}")
                try:
                    p = await get_project(project_id)
                    if p and p.get("status") != ProjectStatus.COMPLETED.value:
                        await update_project_status(project_id, ProjectStatus.FAILED.value)
                except Exception as update_err:
                    logger.error(f"Failed to set project status FAILED for project {project_id}: {update_err}")

                await self._notify("error", project_id, {
                    "role": "orchestrator",
                    "message": f"Pipeline execution error: {clean_msg}"
                })
            finally:
                self._active_executions.discard(project_id)

        task = asyncio.create_task(_run())
        self._running_tasks[project_id] = task

    async def _finalize_project(self, project_id: str, execution_id: Optional[str] = None):
        try:
            from app.services.sandbox_manager import sandbox_manager
            await sandbox_manager.kill(project_id)
        except Exception:
            pass

        try:
            from app.core.database import get_project_outputs, get_memory as get_mem
            all_outputs = await get_project_outputs(project_id)
            all_memory = await get_mem(project_id)
            proj = await get_project(project_id)
            generate_docx(project_id, proj, all_outputs, all_memory)
            await self._notify("docx_generated", project_id, {
                "message": "Project report (.docx) generated and ready for download!"
            })
        except Exception as e:
            await self._notify("error", project_id, {
                "message": f"DOCX generation error: {str(e)}"
            })

        await update_project_status(project_id, ProjectStatus.COMPLETED.value)

        try:
            from app.services.domain_memory import extract_learnings
            saved_learnings = await extract_learnings(project_id)
            if saved_learnings:
                await self._notify("domain_memory", project_id, {
                    "message": f"Extracted {len(saved_learnings)} learnings for future projects."
                })
        except Exception as e:
            logger.warning(f"Domain learning extraction failed (non-critical): {e}")

        try:
            await send_agent_event("project_completed", project_id, "all", None, None)
        except Exception:
            pass

        try:
            proj_data = await get_project(project_id)
            p_name = proj_data.get("problem_statement", "Project")[:60] if proj_data else "Project"
            mem = await get_memory(project_id)
            route = mem.get("pipeline_route", "full")
            from app.services.task_router import get_route_agents
            agents_in_route = get_route_agents(route)
            delivs = ["report.docx"]
            if "engineer" in agents_in_route:
                delivs.insert(0, "code.zip")
            if "ppt" in agents_in_route:
                delivs.append("presentation.pptx")
            await send_deliverables_ready(project_id, p_name, delivs)
        except Exception:
            pass

        await self._notify("project_completed", project_id, {
            "message": "All work is complete! Your project is ready."
        })

    async def handle_approval(self, project_id: str, output_id: str, approved: bool, feedback: str | None = None, execution_id: Optional[str] = None):
        exec_id = execution_id
        if not exec_id:
            mem = await get_memory(project_id)
            exec_id = mem.get("active_execution_id")

        if approved:
            await update_output_status(output_id, "approved")

            project = await get_project(project_id)
            if not project:
                return

            status = project["status"]

            current_role_enum = None
            for r in PIPELINE_ORDER:
                rs = REVIEW_STAGES.get(r)
                if rs and status == rs.value:
                    current_role_enum = r
                    break
            try:
                await send_approval_event(project_id, current_role_enum.value if current_role_enum else "unknown", True)
            except Exception:
                pass

            if status == ProjectStatus.ENGINEER_REVIEW.value:
                engineer_output = await get_latest_output(project_id, AgentRole.ENGINEER.value)
                if engineer_output and isinstance(engineer_output.get("content"), dict):
                    content = dict(engineer_output["content"])
                    mem = await get_memory(project_id)
                    repaired_json = mem.get("repaired_files")
                    if repaired_json:
                        try:
                            repaired = json.loads(repaired_json)
                            if repaired:
                                content["files"] = repaired
                                logger.info(f"Using {len(repaired)} repaired files for project {project_id}")
                        except Exception:
                            pass
                    if content.get("files"):
                        try:
                            zip_path = generate_project_files(project_id, content)
                            files_list = get_generated_files_list(project_id)
                            await self._notify("files_generated", project_id, {
                                "message": f"Project files generated! {len(files_list)} files ready for download.",
                                "files": files_list,
                            })
                        except Exception as e:
                            await self._notify("error", project_id, {
                                "message": f"File generation error: {str(e)}"
                            })
                    if content.get("n8n_workflow"):
                        try:
                            wf_path = generate_workflow_json(project_id, content)
                            if wf_path:
                                await self._notify("workflow_generated", project_id, {
                                    "message": "n8n workflow JSON generated! Ready for import into n8n.",
                                })
                        except Exception as e:
                            await self._notify("error", project_id, {
                                "message": f"Workflow JSON generation error: {str(e)}"
                            })

            next_role = None
            if current_role_enum:
                mem_data = await get_memory(project_id)
                route_name = mem_data.get("pipeline_route", "full")
                from app.services.task_router import get_route_agents
                route_agents = get_route_agents(route_name)

                try:
                    idx = route_agents.index(current_role_enum.value)
                    if idx + 1 < len(route_agents):
                        next_role = AgentRole(route_agents[idx + 1])
                except ValueError:
                    pass

            if next_role:
                await self._notify("approval_accepted", project_id, {
                    "message": f"Approved! Moving to {next_role.value.replace('_', ' ').title()}..."
                })
                await self._start_next_agent(project_id, next_role, execution_id=exec_id)
            else:
                await self._notify("approval_accepted", project_id, {
                    "message": "Approved! Finalizing project..."
                })
                await self._finalize_project(project_id, execution_id=exec_id)
        else:
            await update_output_status(output_id, "rejected")

            project = await get_project(project_id)
            if not project:
                return

            status = project["status"]

            try:
                rejected_role = None
                for r in PIPELINE_ORDER:
                    rs = REVIEW_STAGES.get(r)
                    if rs and status == rs.value:
                        rejected_role = r.value
                        break
                await send_approval_event(project_id, rejected_role or "unknown", False, feedback)
            except Exception:
                pass

            redo_role = None

            if status == ProjectStatus.BA_REVIEW.value:
                redo_role = AgentRole.BUSINESS_ANALYST
            elif status == ProjectStatus.RESEARCH_REVIEW.value:
                redo_role = AgentRole.RESEARCHER
            elif status == ProjectStatus.ARCHITECT_REVIEW.value:
                redo_role = AgentRole.ARCHITECT
            elif status == ProjectStatus.ENGINEER_REVIEW.value:
                redo_role = AgentRole.ENGINEER

            if redo_role and feedback:
                await set_memory(project_id, f"{redo_role.value}_revision_feedback", feedback, "founder")

            if redo_role:
                await self._notify("revision_requested", project_id, {
                    "role": redo_role.value,
                    "message": f"Revision requested. {redo_role.value.replace('_', ' ').title()} is reworking..."
                })
                await self._start_next_agent(project_id, redo_role, execution_id=exec_id)

    async def get_project_state(self, project_id: str) -> dict:
        from app.core.database import get_project_outputs
        project = await get_project(project_id)
        if not project:
            return {}

        outputs = await get_project_outputs(project_id)
        memory = await get_memory(project_id)

        current_agent = None
        pending_approval = False
        status = project["status"]

        for role in PIPELINE_ORDER:
            if status == WORKING_STAGES.get(role, "").value if WORKING_STAGES.get(role) else False:
                current_agent = role.value
            if status == REVIEW_STAGES.get(role, "").value if REVIEW_STAGES.get(role) else False:
                pending_approval = True
                current_agent = role.value

        return {
            "project": project,
            "outputs": outputs,
            "memory": memory,
            "current_agent": current_agent,
            "pending_approval": pending_approval,
        }


orchestrator = Orchestrator()
