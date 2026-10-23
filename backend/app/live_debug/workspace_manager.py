"""
Isolated Workspace Manager for Candidate Patch Application and Verification.
Provides disposable, isolated copies of the live-lab application in workspaces/.
Guarantees RootTrace never writes patches to its own codebase or directly to live-lab before verification.
"""
import os
import shutil
import uuid
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("roottrace.live_debug.workspace")


class WorkspaceManager:
    """
    Manages disposable workspaces in the workspaces/ directory.
    """

    def __init__(self, base_workspaces_dir: Optional[str] = None):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.workspaces_root = base_workspaces_dir or os.path.join(repo_root, "workspaces")
        self.source_dir = os.path.join(repo_root, "live-lab")
        os.makedirs(self.workspaces_root, exist_ok=True)

    def create_isolated_workspace(self, run_id: Optional[str] = None) -> str:
        """
        Creates a disposable isolated copy of live-lab for candidate patch validation.
        Returns the absolute path to the workspace.
        """
        w_id = run_id or f"ws_{uuid.uuid4().hex[:8]}"
        target_path = os.path.join(self.workspaces_root, w_id)

        # Path traversal prevention
        real_target = os.path.realpath(target_path)
        real_root = os.path.realpath(self.workspaces_root)
        if not real_target.startswith(real_root):
            raise ValueError(f"Security error: Workspace target '{target_path}' escapes workspaces directory.")

        if os.path.exists(target_path):
            shutil.rmtree(target_path, ignore_errors=True)

        # Copy live-lab source
        shutil.copytree(
            self.source_dir,
            target_path,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".git*")
        )
        logger.info(f"Created isolated workspace at: {target_path}")
        return target_path

    def create_snapshot(self, workspace_path: str, snapshot_name: str = "pre_patch") -> str:
        """Saves a rollback snapshot of the workspace."""
        snap_path = f"{workspace_path}_{snapshot_name}"
        if os.path.exists(snap_path):
            shutil.rmtree(snap_path, ignore_errors=True)
        shutil.copytree(workspace_path, snap_path)
        return snap_path

    def rollback(self, workspace_path: str, snapshot_name: str = "pre_patch") -> bool:
        """Restores the workspace to the pre-patch snapshot."""
        snap_path = f"{workspace_path}_{snapshot_name}"
        if not os.path.exists(snap_path):
            logger.warning(f"No rollback snapshot found at {snap_path}")
            return False

        shutil.rmtree(workspace_path, ignore_errors=True)
        shutil.copytree(snap_path, workspace_path)
        logger.info(f"Rolled back workspace {workspace_path} from snapshot {snap_path}")
        return True

    def cleanup(self, workspace_path: str):
        """Removes the isolated workspace and associated snapshots."""
        try:
            if os.path.exists(workspace_path):
                shutil.rmtree(workspace_path, ignore_errors=True)
            snap_path = f"{workspace_path}_pre_patch"
            if os.path.exists(snap_path):
                shutil.rmtree(snap_path, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup workspace {workspace_path}: {e}")
