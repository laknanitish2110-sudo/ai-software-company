import asyncio
import json
import logging
from typing import Callable, Awaitable

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
from app.agents.engine import run_agent, cross_review
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


WSCallback = Callable[[str, str, dict], Awaitable[None]]


class Orchestrator:
    def __init__(self):
        self._ws_callback: WSCallback | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}

    def set_ws_callback(self, callback: WSCallback):
        self._ws_callback = callback

    async def _notify(self, msg_type: str, project_id: str, data: dict):
        if self._ws_callback:
            await self._ws_callback(msg_type, project_id, data)

    async def start_project(self, problem_statement: str) -> dict:
        project = await create_project(problem_statement)
        project_id = project["id"]

        await set_memory(project_id, "problem_statement", problem_statement, "founder")

        # Step 1: CEO runs FIRST — breaks problem into components and classifies deliverable type
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
                "message": f"RAG searched {len(components)} components across 19,500+ workflows: {workflow_analysis['summary']}",
                "total_matches": workflow_analysis["total_matches"],
                "categories": workflow_analysis["categories_matched"],
                "deliverable_type": deliverable_type,
            })
        except Exception as e:
            logger.warning(f"Workflow analysis failed (non-critical): {e}")

        await self._start_next_agent(project_id, AgentRole.BUSINESS_ANALYST)

        return project

    async def _start_next_agent(self, project_id: str, role: AgentRole):
        working_status = WORKING_STAGES.get(role)
        if working_status:
            await update_project_status(project_id, working_status.value)

        await self._notify("agent_started", project_id, {
            "role": role.value,
            "message": f"{role.value.replace('_', ' ').title()} is now working..."
        })

        async def _run():
            try:
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
                await self._notify("error", project_id, {
                    "role": role.value,
                    "message": f"Error: {str(e)}"
                })

        task = asyncio.create_task(_run())
        self._running_tasks[project_id] = task

    async def handle_approval(self, project_id: str, output_id: str, approved: bool, feedback: str | None = None):
        if approved:
            await update_output_status(output_id, "approved")

            project = await get_project(project_id)
            if not project:
                return

            status = project["status"]

            current_role = None
            for r in PIPELINE_ORDER:
                rs = REVIEW_STAGES.get(r)
                if rs and status == rs.value:
                    current_role = r.value
                    break
            try:
                await send_approval_event(project_id, current_role or "unknown", True)
            except Exception:
                pass

            next_role = None

            if status == ProjectStatus.BA_REVIEW.value:
                next_role = AgentRole.RESEARCHER
            elif status == ProjectStatus.RESEARCH_REVIEW.value:
                next_role = AgentRole.ARCHITECT
            elif status == ProjectStatus.ARCHITECT_REVIEW.value:
                next_role = AgentRole.ENGINEER
            elif status == ProjectStatus.ENGINEER_REVIEW.value:
                engineer_output = await get_latest_output(project_id, AgentRole.ENGINEER.value)
                if engineer_output and isinstance(engineer_output.get("content"), dict):
                    content = engineer_output["content"]
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
                next_role = AgentRole.PPT

            if next_role:
                await self._notify("approval_accepted", project_id, {
                    "message": f"Approved! Moving to {next_role.value.replace('_', ' ').title()}..."
                })
                await self._start_next_agent(project_id, next_role)
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
                await self._start_next_agent(project_id, redo_role)

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
