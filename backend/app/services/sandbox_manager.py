import asyncio
import logging
import os
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

PREVIEW_TIMEOUT_SECONDS = int(os.getenv("SANDBOX_PREVIEW_TIMEOUT", "600"))


class SandboxManager:
    """Tracks active E2B sandboxes kept alive for live preview."""

    def __init__(self):
        self._active: Dict[str, dict] = {}

    def register(self, project_id: str, sbx: Any, preview_url: str, port: int):
        self._cleanup_existing(project_id)
        cleanup_task = asyncio.create_task(self._auto_cleanup(project_id))
        self._active[project_id] = {
            "sbx": sbx,
            "url": preview_url,
            "port": port,
            "task": cleanup_task,
        }
        logger.info(f"Sandbox registered for preview: project={project_id}, url={preview_url}, timeout={PREVIEW_TIMEOUT_SECONDS}s")

    async def _auto_cleanup(self, project_id: str):
        await asyncio.sleep(PREVIEW_TIMEOUT_SECONDS)
        await self.kill(project_id)

    async def kill(self, project_id: str):
        entry = self._active.pop(project_id, None)
        if entry:
            entry["task"].cancel()
            try:
                await asyncio.to_thread(entry["sbx"].kill)
                logger.info(f"Sandbox killed for project {project_id}")
            except Exception as e:
                logger.warning(f"Error killing sandbox for {project_id}: {e}")

    def _cleanup_existing(self, project_id: str):
        entry = self._active.get(project_id)
        if entry:
            entry["task"].cancel()
            try:
                import threading
                threading.Thread(target=entry["sbx"].kill, daemon=True).start()
            except Exception:
                pass
            del self._active[project_id]

    def get_preview_url(self, project_id: str) -> Optional[str]:
        entry = self._active.get(project_id)
        return entry["url"] if entry else None

    def is_active(self, project_id: str) -> bool:
        return project_id in self._active


sandbox_manager = SandboxManager()
