"""
Patch Manager for RootTrace Live.
Handles unified diff parsing, SHA-256 patch hashing, validation, and safe application
to isolated workspaces with rollback capabilities.
"""
import os
import re
import hashlib
import logging
from typing import Dict, List, Optional, Tuple, Any
from pydantic import BaseModel, Field

from .output_validator import OutputValidator, OutputValidationResult

logger = logging.getLogger("roottrace.live_debug.patch")


class PatchProposal(BaseModel):
    id: str
    run_id: str
    title: str
    explanation: str
    diff: str
    patch_hash: str
    target_workspace: str
    target_files: List[str]
    is_critic_approved: bool = True
    is_policy_approved: bool = True
    created_at: str


class PatchApplicationResult(BaseModel):
    success: bool
    patch_hash: str
    modified_files: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    applied_to_workspace: str


class PatchManager:
    """
    Validates and applies patches inside isolated workspaces.
    """

    @staticmethod
    def compute_patch_hash(diff_text: str) -> str:
        """Computes deterministic SHA-256 hash of normalized unified diff."""
        normalized = diff_text.strip().replace("\r\n", "\n")
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def validate_proposal(self, diff_text: str, permitted_workspace: str) -> OutputValidationResult:
        """Validates patch diff against safety rules and path restrictions."""
        return OutputValidator.validate_unified_diff(diff_text, permitted_workspace_root=permitted_workspace)

    def apply_patch_to_workspace(
        self,
        diff_text: str,
        workspace_dir: str,
        expected_patch_hash: Optional[str] = None
    ) -> PatchApplicationResult:
        """
        Safely applies a unified diff to the files inside workspace_dir.
        Verifies expected patch hash before application to prevent tampering.
        """
        actual_hash = self.compute_patch_hash(diff_text)
        if expected_patch_hash and actual_hash != expected_patch_hash:
            return PatchApplicationResult(
                success=False,
                patch_hash=actual_hash,
                error_message=f"Tampering detected: Patch hash mismatch. Expected {expected_patch_hash}, got {actual_hash}",
                applied_to_workspace=workspace_dir
            )

        # Validate with output validator
        val_res = OutputValidator.validate_unified_diff(diff_text, permitted_workspace_root=".")
        if not val_res.is_valid:
            return PatchApplicationResult(
                success=False,
                patch_hash=actual_hash,
                error_message=f"Validation failed: {val_res.rejection_reason}",
                applied_to_workspace=workspace_dir
            )

        # Parse and apply hunks file by file
        try:
            modified_files = self._apply_unified_diff_hunks(diff_text, workspace_dir)
            return PatchApplicationResult(
                success=True,
                patch_hash=actual_hash,
                modified_files=modified_files,
                applied_to_workspace=workspace_dir
            )
        except Exception as e:
            logger.error(f"Failed to apply patch in {workspace_dir}: {e}")
            return PatchApplicationResult(
                success=False,
                patch_hash=actual_hash,
                error_message=f"Patch application failed: {str(e)}",
                applied_to_workspace=workspace_dir
            )

    def _apply_unified_diff_hunks(self, diff_text: str, workspace_dir: str) -> List[str]:
        """
        In-memory hunk patcher for standard unified diff format.
        """
        lines = diff_text.replace("\r\n", "\n").splitlines()
        file_diffs = []
        current_file_lines = []

        for line in lines:
            if line.startswith("--- ") and current_file_lines:
                file_diffs.append(current_file_lines)
                current_file_lines = [line]
            else:
                current_file_lines.append(line)
        if current_file_lines:
            file_diffs.append(current_file_lines)

        modified = []

        for fdiff in file_diffs:
            if len(fdiff) < 2 or not fdiff[0].startswith("--- ") or not fdiff[1].startswith("+++ "):
                continue

            # Extract target path
            raw_path = fdiff[1][4:].strip()
            if raw_path.startswith("b/"):
                raw_path = raw_path[2:]
            # Strip live-lab prefix if present
            if raw_path.startswith("live-lab/"):
                raw_path = raw_path[9:]

            target_file_path = os.path.join(workspace_dir, raw_path)
            real_target = os.path.realpath(target_file_path)
            real_ws = os.path.realpath(workspace_dir)
            if not real_target.startswith(real_ws):
                raise ValueError(f"Target path '{raw_path}' escapes workspace directory.")

            if not os.path.exists(target_file_path):
                raise FileNotFoundError(f"Target file to patch does not exist: {raw_path}")

            with open(target_file_path, "r", encoding="utf-8") as f:
                original_content = f.read().replace("\r\n", "\n").splitlines()

            new_content = self._patch_lines(original_content, fdiff[2:])
            with open(target_file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_content) + "\n")

            modified.append(raw_path)

        return modified

    def _patch_lines(self, original_lines: List[str], hunk_lines: List[str]) -> List[str]:
        """Applies hunks to line list."""
        out_lines = list(original_lines)
        idx = 0
        hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

        i = 0
        while i < len(hunk_lines):
            line = hunk_lines[i]
            m = hunk_re.match(line)
            if m:
                orig_start = int(m.group(1)) - 1
                i += 1
                # Collect hunk lines
                hunk_body = []
                while i < len(hunk_lines) and not hunk_re.match(hunk_lines[i]):
                    hunk_body.append(hunk_lines[i])
                    i += 1

                # Apply this hunk
                out_lines = self._apply_single_hunk(out_lines, orig_start, hunk_body)
            else:
                i += 1

        return out_lines

    def _apply_single_hunk(self, lines: List[str], start_idx: int, hunk: List[str]) -> List[str]:
        # Context lines and removals
        expected_orig = []
        replacement = []
        for hline in hunk:
            if hline.startswith(" "):
                expected_orig.append(hline[1:])
                replacement.append(hline[1:])
            elif hline.startswith("-"):
                expected_orig.append(hline[1:])
            elif hline.startswith("+"):
                replacement.append(hline[1:])

        # Find matching location around start_idx
        found_idx = -1
        search_range = range(max(0, start_idx - 5), min(len(lines), start_idx + 6))
        for s in search_range:
            if lines[s:s + len(expected_orig)] == expected_orig:
                found_idx = s
                break

        if found_idx == -1:
            # Fallback search whole file
            for s in range(len(lines) - len(expected_orig) + 1):
                if lines[s:s + len(expected_orig)] == expected_orig:
                    found_idx = s
                    break

        if found_idx != -1:
            return lines[:found_idx] + replacement + lines[found_idx + len(expected_orig):]
        else:
            # If not exact match, simple replacement if within bounds
            if start_idx < len(lines):
                return lines[:start_idx] + replacement + lines[start_idx + len(expected_orig):]
            return lines + replacement
