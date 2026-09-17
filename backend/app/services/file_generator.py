import os
import json
from pathlib import Path
from app.core.artifact_store import get_artifact_store, PROJECTS_DIR

async def ensure_projects_dir():
    # Deprecated: Artifact store handles its own initialization
    pass

async def generate_project_files(project_id: str, engineer_output: dict) -> str | None:
    """
    Writes the engineer's generated files to the ArtifactStore.
    Returns None since there is no longer a local zip file path to return.
    """
    if "files" not in engineer_output or not isinstance(engineer_output["files"], list):
        return None

    store = get_artifact_store()
    
    for file_obj in engineer_output["files"]:
        path = file_obj.get("path")
        content = file_obj.get("content")
        if not path or content is None:
            continue
            
        # Prevent path traversal
        if ".." in path or path.startswith("/"):
            continue

        await store.write_file(project_id, path, content)

    setup = engineer_output.get("setup_instructions", "")
    if setup:
        readme_parts = []
        project_name = engineer_output.get("project_structure", "Project")
        if isinstance(project_name, str):
            readme_parts.append(f"# {project_name}\n")
        readme_parts.append("## Setup Instructions\n")
        if isinstance(setup, list):
            for step in setup:
                readme_parts.append(f"- {step}")
        else:
            readme_parts.append(str(setup))

        run_commands = engineer_output.get("run_commands", [])
        if run_commands:
            readme_parts.append("\n## Run\n")
            if isinstance(run_commands, list):
                for cmd in run_commands:
                    readme_parts.append(f"```\n{cmd}\n```")
            else:
                readme_parts.append(f"```\n{run_commands}\n```")

        env_vars = engineer_output.get("environment_variables", [])
        if env_vars:
            readme_parts.append("\n## Environment Variables\n")
            if isinstance(env_vars, list):
                for var in env_vars:
                    if isinstance(var, dict):
                        readme_parts.append(f"- `{var.get('name', '')}`: {var.get('description', '')}")
                    else:
                        readme_parts.append(f"- {var}")
            elif isinstance(env_vars, dict):
                for k, v in env_vars.items():
                    readme_parts.append(f"- `{k}`: {v}")

        setup_readme_path = "SETUP.md"
        if not await store.file_exists(project_id, "README.md"):
            setup_readme_path = "README.md"
        await store.write_file(project_id, setup_readme_path, "\n".join(readme_parts))

    return None

def get_project_zip_path(project_id: str) -> str | None:
    # Deprecated: zip files are streamed on the fly via ArtifactStore
    return None

async def get_generated_files_list(project_id: str) -> list[str]:
    store = get_artifact_store()
    return await store.list_files(project_id)

async def get_generated_file_contents(project_id: str) -> list[dict]:
    store = get_artifact_store()
    file_paths = await store.list_files(project_id)
    files = []
    
    for rel_path in sorted(file_paths):
        try:
            raw_bytes = await store.read_file(project_id, rel_path)
            size = len(raw_bytes)
            try:
                content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = "(binary file)"
        except OSError:
            content = "(error reading)"
            size = 0
            
        ext = rel_path.split(".")[-1] if "." in rel_path else ""
        lang_map = {
            "py": "python", "js": "javascript", "ts": "typescript",
            "tsx": "tsx", "jsx": "jsx", "html": "html", "css": "css",
            "json": "json", "md": "markdown", "yml": "yaml", "yaml": "yaml",
            "toml": "toml", "sql": "sql", "sh": "bash", "env": "bash",
            "txt": "text", "cfg": "ini", "ini": "ini", "dockerfile": "dockerfile",
        }
        language = lang_map.get(ext, ext or "text")
        files.append({
            "path": rel_path,
            "size": size,
            "content": content,
            "language": language,
        })
    return files

