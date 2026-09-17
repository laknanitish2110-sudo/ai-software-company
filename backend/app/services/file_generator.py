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


MAX_APPLY_FILES = 200
MAX_APPLY_FILE_SIZE = 500 * 1024
MAX_APPLY_TOTAL_SIZE = 50 * 1024 * 1024


def _is_safe_path(project_dir: Path, file_path: str) -> Path | None:
    cleaned = file_path.replace("\\", "/").lstrip("/")
    if not cleaned or ".." in cleaned.split("/"):
        return None
    full_path = (project_dir / cleaned).resolve()
    try:
        full_path.relative_to(project_dir.resolve())
    except ValueError:
        return None
    return full_path


def generate_deployable_bundle(project_id: str, artifacts: list[dict]) -> str:
    import shutil, zipfile
    PROJECTS_DIR.mkdir(exist_ok=True)
    bundle_dir = PROJECTS_DIR / f"{project_id}_bundle"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)
    for entry in artifacts:
        fp = entry.get("path", "")
        content = entry.get("content", "")
        if not fp or not content:
            continue
        full_path = _is_safe_path(bundle_dir, fp)
        if not full_path:
            continue
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
    zip_path = PROJECTS_DIR / f"{project_id}_bundle.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in bundle_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(bundle_dir))
    return str(zip_path)


def get_deployable_bundle_path(project_id: str) -> str | None:
    zip_path = PROJECTS_DIR / f"{project_id}_bundle.zip"
    if zip_path.exists():
        return str(zip_path)
    return None


def apply_file_updates(project_id: str, file_updates: list[dict]) -> dict:
    import shutil, zipfile
    if len(file_updates) > MAX_APPLY_FILES:
        return {"status": "error", "message": f"Too many files (max {MAX_APPLY_FILES})"}
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        return {"status": "error", "message": "Project files not found"}
    backup_dir = PROJECTS_DIR / f"{project_id}_backup"
    try:
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        import shutil as _s
        _s.copytree(project_dir, backup_dir)
    except OSError:
        return {"status": "error", "message": "Failed to create safety snapshot"}
    total_size = 0
    updated = []
    skipped = []
    try:
        for entry in file_updates:
            path = entry.get("path", "")
            if not path:
                continue
            if "content" not in entry:
                skipped.append(path)
                continue
            full_path = _is_safe_path(project_dir, path)
            if not full_path:
                skipped.append(path)
                continue
            content = entry["content"]
            content_bytes = content.encode("utf-8") if isinstance(content, str) else b""
            if len(content_bytes) > MAX_APPLY_FILE_SIZE:
                skipped.append(path)
                continue
            total_size += len(content_bytes)
            if total_size > MAX_APPLY_TOTAL_SIZE:
                raise ValueError("Total payload size exceeds limit")
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(content_bytes)
            updated.append(path)
        zip_path = PROJECTS_DIR / f"{project_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in project_dir.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(project_dir))
    except Exception:
        shutil.rmtree(project_dir)
        shutil.move(str(backup_dir), str(project_dir))
        return {"status": "error", "message": "Apply failed, project restored from snapshot"}
    shutil.rmtree(backup_dir, ignore_errors=True)
    result = {"status": "ok", "updated_files": updated, "count": len(updated)}
    if skipped:
        result["skipped"] = skipped
    return result
