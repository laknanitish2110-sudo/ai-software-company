import os
import io
import shutil
import zipfile
from typing import AsyncGenerator
from pathlib import Path

PROJECTS_DIR = Path("generated_projects")

class ArtifactStore:
    async def write_file(self, project_id: str, path: str, content: str | bytes):
        raise NotImplementedError
        
    async def read_file(self, project_id: str, path: str) -> bytes:
        raise NotImplementedError
        
    async def file_exists(self, project_id: str, path: str) -> bool:
        raise NotImplementedError
        
    async def list_files(self, project_id: str) -> list[str]:
        raise NotImplementedError
        
    async def get_project_archive(self, project_id: str) -> AsyncGenerator[bytes, None]:
        raise NotImplementedError
        
    async def delete_project(self, project_id: str):
        raise NotImplementedError

class LocalArtifactStore(ArtifactStore):
    async def write_file(self, project_id: str, path: str, content: str | bytes):
        target_path = PROJECTS_DIR / project_id / path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            target_path.write_bytes(content.encode("utf-8"))
        else:
            target_path.write_bytes(content)
            
    async def read_file(self, project_id: str, path: str) -> bytes:
        target_path = PROJECTS_DIR / project_id / path
        if not target_path.exists():
            raise FileNotFoundError(f"File {path} not found in project {project_id}")
        return target_path.read_bytes()
        
    async def file_exists(self, project_id: str, path: str) -> bool:
        return (PROJECTS_DIR / project_id / path).exists()
        
    async def list_files(self, project_id: str) -> list[str]:
        project_dir = PROJECTS_DIR / project_id
        if not project_dir.exists():
            return []
            
        file_list = []
        for root, _, filenames in os.walk(project_dir):
            for fname in filenames:
                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, project_dir)
                file_list.append(rel_path.replace("\\", "/"))
        return file_list

    async def get_project_archive(self, project_id: str) -> AsyncGenerator[bytes, None]:
        project_dir = PROJECTS_DIR / project_id
        if not project_dir.exists():
            raise FileNotFoundError(f"Project {project_id} not found")
            
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, filenames in os.walk(project_dir):
                for fname in filenames:
                    full_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(full_path, project_dir)
                    zipf.write(full_path, rel_path)
                    
        buffer.seek(0)
        yield buffer.read()
        
    async def delete_project(self, project_id: str):
        project_dir = PROJECTS_DIR / project_id
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)

def get_artifact_store() -> ArtifactStore:
    return LocalArtifactStore()
