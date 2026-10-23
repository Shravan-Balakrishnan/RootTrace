"""
LLM Output Guardrails and Unified Diff Validator for RootTrace.
Validates all AI structured responses (hypotheses, diagnoses, patch proposals):
- Verifies cited evidence IDs actually exist in the current run's collected evidence.
- Rejects malformed unified diffs, path traversal, out-of-scope files, and RootTrace self-modification.
- Ensures the Critic evaluation and deterministic policy gates pass before any patch can be approved.
"""
from typing import Dict, List, Set, Optional, Tuple, Any
import re
import os
import hashlib
from pydantic import BaseModel, Field

# Disallowed paths that an AI patch must NEVER touch
PROTECTED_PATHS = [
    "backend/",
    "frontend/",
    "tests/",
    ".git/",
    ".github/",
    ".env",
    "sessions.db"
]

MAX_PATCH_BYTES = 32768      # 32 KB maximum diff size
MAX_FILES_PER_PATCH = 3      # Maximum number of modified files per patch proposal


class OutputValidationResult(BaseModel):
    is_valid: bool
    rejection_reason: Optional[str] = None
    validated_evidence_ids: List[str] = Field(default_factory=list)
    invalid_evidence_ids: List[str] = Field(default_factory=list)
    target_files: List[str] = Field(default_factory=list)
    patch_hash: Optional[str] = None


class OutputValidator:
    """
    Validates model outputs, cited evidence references, and patch diffs.
    """

    @staticmethod
    def validate_evidence_references(
        cited_evidence_ids: List[str],
        known_evidence_ids: Set[str]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Ensures that every evidence ID cited by the model actually exists in the current run.
        Rejects fabricated or cross-investigation evidence IDs.
        """
        valid_ids: List[str] = []
        invalid_ids: List[str] = []

        for cid in cited_evidence_ids:
            if cid in known_evidence_ids:
                valid_ids.append(cid)
            else:
                invalid_ids.append(cid)

        is_all_valid = len(invalid_ids) == 0
        return is_all_valid, valid_ids, invalid_ids

    @staticmethod
    def validate_unified_diff(
        diff_text: str,
        permitted_workspace_root: str = "live-lab"
    ) -> OutputValidationResult:
        """
        Strictly validates a proposed patch unified diff:
        - Must follow standard unified diff structure (--- and +++ headers)
        - Must not modify protected RootTrace files
        - Must not perform path traversal (../ or absolute paths)
        - Must only target files inside permitted_workspace_root
        - Must stay within size and file-count bounds
        - Generates SHA-256 hash of the normalized diff
        """
        if not diff_text or not diff_text.strip():
            return OutputValidationResult(
                is_valid=False,
                rejection_reason="Patch diff is empty."
            )

        diff_bytes = diff_text.encode("utf-8")
        if len(diff_bytes) > MAX_PATCH_BYTES:
            return OutputValidationResult(
                is_valid=False,
                rejection_reason=f"Patch size ({len(diff_bytes)} bytes) exceeds maximum limit of {MAX_PATCH_BYTES} bytes."
            )

        # Parse target file headers: --- a/path and +++ b/path
        file_header_re = re.compile(r"^--- (?:a/)?([^\r\n\t]+)\r?\n\+\+\+ (?:b/)?([^\r\n\t]+)", re.MULTILINE)
        matches = file_header_re.findall(diff_text)

        if not matches:
            return OutputValidationResult(
                is_valid=False,
                rejection_reason="Invalid unified diff format: missing standard '--- a/...' and '+++ b/...' headers."
            )

        if len(matches) > MAX_FILES_PER_PATCH:
            return OutputValidationResult(
                is_valid=False,
                rejection_reason=f"Patch modifies {len(matches)} files, which exceeds the limit of {MAX_FILES_PER_PATCH}."
            )

        target_files: List[str] = []

        for old_file, new_file in matches:
            # Clean paths
            target_path = new_file.strip().replace("\\", "/")
            if target_path.startswith("b/"):
                target_path = target_path[2:]

            # 1. Path traversal check
            if ".." in target_path or target_path.startswith("/") or re.match(r"^[a-zA-Z]:", target_path):
                return OutputValidationResult(
                    is_valid=False,
                    rejection_reason=f"Path traversal or absolute path detected in patch target: '{target_path}'"
                )

            # 2. Protected files / RootTrace self-modification check
            for protected in PROTECTED_PATHS:
                if target_path.lower().startswith(protected.lower()):
                    return OutputValidationResult(
                        is_valid=False,
                        rejection_reason=f"CRITICAL SAFETY VIOLATION: Patch attempts to modify protected RootTrace file '{target_path}'."
                    )

            # 3. Permitted workspace scope check
            # Permitted targets are inside live-lab (or workspace relative paths)
            normalized_permitted = permitted_workspace_root.replace("\\", "/").rstrip("/")
            if not target_path.startswith(normalized_permitted) and not target_path.startswith("app/") and not target_path.startswith("tests/"):
                return OutputValidationResult(
                    is_valid=False,
                    rejection_reason=f"Scope violation: Patch target '{target_path}' is outside permitted workspace '{permitted_workspace_root}'."
                )

            target_files.append(target_path)

        # 4. Check for hunk headers (@@ -start,len +start,len @@)
        hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", re.MULTILINE)
        if not hunk_re.search(diff_text):
            return OutputValidationResult(
                is_valid=False,
                rejection_reason="Malformed patch diff: missing valid @@ hunk headers."
            )

        # 5. Compute deterministic SHA-256 hash of normalized diff
        norm_diff = diff_text.strip().replace("\r\n", "\n")
        patch_hash = hashlib.sha256(norm_diff.encode("utf-8")).hexdigest()

        return OutputValidationResult(
            is_valid=True,
            target_files=target_files,
            patch_hash=patch_hash
        )

    @staticmethod
    def validate_critic_approval(critic_eval: Any) -> Tuple[bool, Optional[str]]:
        """
        Ensures the Critic evaluation does not contain active vetos or critical contradictions
        before a diagnosis or patch can be presented.
        """
        if not critic_eval:
            return False, "Missing Critic evaluation."

        contradictions = getattr(critic_eval, "contradictions_found", [])
        if contradictions:
            return False, f"Critic vetoed diagnosis due to contradiction: {contradictions[0]}"

        has_falsified = getattr(critic_eval, "has_falsified_leading_hypothesis", False)
        is_valid = getattr(critic_eval, "is_valid_candidate", True)
        if has_falsified or not is_valid:
            return False, "Critic explicitly falsified the leading hypothesis."

        return True, None
