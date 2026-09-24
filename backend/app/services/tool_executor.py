"""
Tool execution layer for persistent AI employees.

Defines tool schemas (OpenAI function-calling format), dispatches tool calls
through the permission system, and delegates to existing services.
"""

import json
import logging
from typing import Any

from app.core.database import check_permission
from app.core.artifact_store import LocalArtifactStore

logger = logging.getLogger(__name__)

EMPLOYEE_ROLE_TO_ENGINE_ROLE = {
    "business analyst": "business_analyst",
    "researcher": "researcher",
    "architect": "architect",
    "software engineer": "engineer",
    "qa engineer": "engineer",
    "technical writer": "business_analyst",
}


def get_tools_for_employee(allowed_tool_names: list[str] | None) -> list[dict]:
    """Filter TOOL_SCHEMAS to only the tools this employee is allowed to see."""
    if not allowed_tool_names:
        return TOOL_SCHEMAS
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in allowed_tool_names]


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_code",
            "description": "Execute code in a sandboxed environment (E2B). Use this to run Python or Node.js code, install packages, or test implementations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "enum": ["python", "javascript", "bash"],
                        "description": "Programming language to execute",
                    },
                    "code": {
                        "type": "string",
                        "description": "The code to execute",
                    },
                    "packages": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Packages to install before running (e.g. ['requests', 'pandas'])",
                    },
                },
                "required": ["language", "code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the project's artifact store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the project root (e.g. 'src/app.py')",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or create a file in the project's artifact store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the project root",
                    },
                    "content": {
                        "type": "string",
                        "description": "The file content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the project's artifact store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Optional subdirectory to list (default: project root)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_read",
            "description": "Read repository info, file contents, or list files from a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner (username or org)",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory path within the repo (empty string for root listing)",
                    },
                },
                "required": ["owner", "repo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_push",
            "description": "Push files to a GitHub repository. Creates the repo if it doesn't exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "owner": {
                        "type": "string",
                        "description": "Repository owner",
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name",
                    },
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["path", "content"],
                        },
                        "description": "Files to push",
                    },
                    "commit_message": {
                        "type": "string",
                        "description": "Git commit message",
                    },
                },
                "required": ["owner", "repo", "files", "commit_message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information on a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_pipeline",
            "description": "Trigger the AI software-building pipeline to build a complete project. This runs the full team: Business Analyst, Researcher, Architect, Engineer, QA — producing working code, tests, and documentation. Use this for substantial build requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem_statement": {
                        "type": "string",
                        "description": "What to build — a clear description of the software project or feature",
                    },
                    "route": {
                        "type": "string",
                        "enum": ["full", "standard", "quick_build", "backend_only", "frontend_only"],
                        "description": "Pipeline route. 'full' runs all agents, 'quick_build' skips research/analysis for speed",
                    },
                },
                "required": ["problem_statement"],
            },
        },
    },
]

TOOL_PERMISSION_MAP = {
    "run_code": ("e2b", "execute"),
    "read_file": ("files", "read"),
    "write_file": ("files", "write"),
    "list_files": ("files", "read"),
    "github_read": ("github", "read"),
    "github_push": ("github", "write"),
    "web_search": ("web_search", "read"),
    "run_pipeline": ("deploy", "execute"),
}


async def check_tool_permission(employee_id: str, tool_name: str) -> str:
    mapping = TOOL_PERMISSION_MAP.get(tool_name)
    if not mapping:
        return "deny"
    tool_category, action = mapping
    return await check_permission(employee_id, tool_category, action)


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    employee_id: str,
    user_id: str,
    project_id: str | None = None,
    github_token: str | None = None,
) -> dict[str, Any]:
    """Execute a tool call after checking permissions. Returns {success, result} or {error}."""

    permission = await check_tool_permission(employee_id, tool_name)
    if permission == "deny":
        return {"success": False, "error": f"Permission denied: {tool_name} is not allowed for this employee."}
    if permission == "ask":
        return {
            "success": False,
            "error": f"Permission required: {tool_name} needs human approval. The user must grant permission before this action can be taken.",
            "needs_approval": True,
            "tool": tool_name,
            "arguments": arguments,
        }

    try:
        if tool_name == "run_code":
            return await _exec_run_code(arguments, project_id)
        elif tool_name == "read_file":
            return await _exec_read_file(arguments, project_id)
        elif tool_name == "write_file":
            return await _exec_write_file(arguments, project_id)
        elif tool_name == "list_files":
            return await _exec_list_files(arguments, project_id)
        elif tool_name == "github_read":
            return await _exec_github_read(arguments, github_token)
        elif tool_name == "github_push":
            return await _exec_github_push(arguments, github_token)
        elif tool_name == "web_search":
            return await _exec_web_search(arguments)
        elif tool_name == "run_pipeline":
            return await _exec_run_pipeline(arguments, user_id, project_id)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        return {"success": False, "error": str(e)}


async def _exec_run_code(args: dict, project_id: str | None) -> dict:
    language = args.get("language", "python")
    code = args["code"]
    packages = args.get("packages", [])

    try:
        from e2b_code_interpreter import Sandbox
    except ImportError:
        return {"success": False, "error": "E2B SDK not available. Install e2b-code-interpreter."}

    import os
    e2b_key = os.getenv("E2B_API_KEY")
    if not e2b_key:
        return {"success": False, "error": "E2B API key not configured."}

    try:
        sbx = Sandbox(api_key=e2b_key)
        try:
            if packages:
                if language == "python":
                    install_cmd = f"pip install {' '.join(packages)}"
                elif language == "javascript":
                    install_cmd = f"npm install {' '.join(packages)}"
                else:
                    install_cmd = None

                if install_cmd:
                    install_result = sbx.commands.run(install_cmd, timeout=60)
                    if install_result.exit_code != 0:
                        return {
                            "success": False,
                            "error": f"Package install failed: {install_result.stderr}",
                        }

            if language == "python":
                execution = sbx.run_code(code)
                stdout = "".join(r.text for r in execution.results) if execution.results else ""
                logs_stdout = "".join(execution.logs.stdout) if execution.logs.stdout else ""
                logs_stderr = "".join(execution.logs.stderr) if execution.logs.stderr else ""
                if execution.error:
                    return {
                        "success": False,
                        "error": f"{execution.error.name}: {execution.error.value}",
                        "stdout": logs_stdout,
                    }
                return {
                    "success": True,
                    "result": stdout or logs_stdout,
                    "stderr": logs_stderr,
                }
            else:
                if language == "javascript":
                    sbx.files.write("/tmp/script.js", code)
                    result = sbx.commands.run("node /tmp/script.js", timeout=30)
                else:
                    sbx.files.write("/tmp/script.sh", code)
                    result = sbx.commands.run("bash /tmp/script.sh", timeout=30)

                return {
                    "success": result.exit_code == 0,
                    "result": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                }
        finally:
            sbx.kill()
    except Exception as e:
        return {"success": False, "error": f"Sandbox error: {e}"}


async def _exec_read_file(args: dict, project_id: str | None) -> dict:
    if not project_id:
        return {"success": False, "error": "No project context — cannot read files."}
    store = LocalArtifactStore()
    path = args["path"]
    try:
        content = await store.read_file(project_id, path)
        return {"success": True, "result": content.decode("utf-8", errors="replace")}
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {path}"}


async def _exec_write_file(args: dict, project_id: str | None) -> dict:
    if not project_id:
        return {"success": False, "error": "No project context — cannot write files."}
    store = LocalArtifactStore()
    path = args["path"]
    content = args["content"]
    await store.write_file(project_id, path, content)
    return {"success": True, "result": f"File written: {path}"}


async def _exec_list_files(args: dict, project_id: str | None) -> dict:
    if not project_id:
        return {"success": False, "error": "No project context."}
    store = LocalArtifactStore()
    files = await store.list_files(project_id)
    directory = args.get("directory", "")
    if directory:
        files = [f for f in files if f.startswith(directory)]
    return {"success": True, "result": files}


async def _exec_github_read(args: dict, github_token: str | None) -> dict:
    if not github_token:
        return {"success": False, "error": "No GitHub token configured. Ask the user to connect their GitHub account."}

    import httpx
    owner = args["owner"]
    repo = args["repo"]
    path = args.get("path", "")

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        res = await client.get(url, headers=headers)
        if res.status_code == 404:
            return {"success": False, "error": f"Not found: {owner}/{repo}/{path}"}
        if res.status_code != 200:
            return {"success": False, "error": f"GitHub API error: {res.status_code}"}

        data = res.json()
        if isinstance(data, list):
            return {"success": True, "result": [{"name": item["name"], "type": item["type"], "path": item["path"]} for item in data]}
        elif data.get("encoding") == "base64":
            import base64
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return {"success": True, "result": content}
        else:
            return {"success": True, "result": data}


async def _exec_github_push(args: dict, github_token: str | None) -> dict:
    if not github_token:
        return {"success": False, "error": "No GitHub token configured."}

    from app.services.github_service import GitHubService
    svc = GitHubService(github_token)

    owner = args["owner"]
    repo = args["repo"]
    files = args["files"]
    commit_msg = args.get("commit_message", "Update from AI employee")

    try:
        commit_sha = await svc.push_files(owner, repo, files, commit_msg)
        return {"success": True, "result": f"Pushed {len(files)} files. Commit: {commit_sha}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _exec_web_search(args: dict) -> dict:
    from app.services.web_search import research_topic
    query = args["query"]
    try:
        results = await research_topic(query)
        return {"success": True, "result": results}
    except Exception as e:
        return {"success": False, "error": f"Search failed: {e}"}


async def _exec_run_pipeline(args: dict, user_id: str, project_id: str | None) -> dict:
    from app.services.orchestrator import orchestrator

    problem = args.get("problem_statement", "")
    if not problem:
        return {"success": False, "error": "problem_statement is required."}
    route = args.get("route", "full")

    try:
        project = await orchestrator.start_project(
            problem_statement=problem,
            user_id=user_id,
            auto_approve=False,
            route=route,
        )
        return {
            "success": True,
            "result": f"Pipeline started! Project ID: {project['id']}. "
                       f"Route: {route}. The team is now working on: {problem[:200]}. "
                       f"Track progress in the Build Room or via /projects/{project['id']}.",
            "project_id": project["id"],
        }
    except ValueError as e:
        if "PROJECT_EXECUTION_IN_PROGRESS" in str(e):
            return {"success": False, "error": "A pipeline is already running. Wait for it to finish."}
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Pipeline start failed: {e}"}
