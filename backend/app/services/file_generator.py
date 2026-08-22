import os
import json
import shutil
import zipfile
from pathlib import Path

PROJECTS_DIR = Path("generated_projects")


def ensure_projects_dir():
    PROJECTS_DIR.mkdir(exist_ok=True)


def generate_project_files(project_id: str, engineer_output: dict) -> str:
    ensure_projects_dir()

    project_dir = PROJECTS_DIR / project_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True)

    files = engineer_output.get("files", [])
    for file_entry in files:
        file_path = file_entry.get("path", "")
        content = file_entry.get("content", "")

        if not file_path or not content:
            continue

        file_path = file_path.lstrip("/").lstrip("\\")
        full_path = project_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

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

        setup_readme = project_dir / "SETUP.md"
        if not (project_dir / "README.md").exists():
            setup_readme = project_dir / "README.md"
        setup_readme.write_text("\n".join(readme_parts), encoding="utf-8")

    zip_path = PROJECTS_DIR / f"{project_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in project_dir.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(project_dir)
                zf.write(file, arcname)

    return str(zip_path)


def get_project_zip_path(project_id: str) -> str | None:
    zip_path = PROJECTS_DIR / f"{project_id}.zip"
    if zip_path.exists():
        return str(zip_path)
    return None


def get_generated_files_list(project_id: str) -> list[dict]:
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        return []

    files = []
    for file in sorted(project_dir.rglob("*")):
        if file.is_file():
            rel_path = str(file.relative_to(project_dir))
            size = file.stat().st_size
            files.append({"path": rel_path, "size": size})
    return files


def get_generated_file_contents(project_id: str) -> list[dict]:
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        return []

    files = []
    for file in sorted(project_dir.rglob("*")):
        if file.is_file():
            rel_path = str(file.relative_to(project_dir))
            size = file.stat().st_size
            content = ""
            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                content = "(binary file)"
            ext = file.suffix.lstrip(".")
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
