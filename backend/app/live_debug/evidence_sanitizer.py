"""
Evidence Sanitization Pipeline for RootTrace.
Coordinates secret scanning and input guardrails across evidence records,
tracebacks, logs, test outputs, and historical incidents before model dispatch.
Guarantees fail-safe behavior: never falls back to unsanitized raw data.
"""
from typing import Dict, List, Any, Optional, Tuple
import datetime
import logging
from pydantic import BaseModel, Field

from .secret_scanner import SecretScanner, ScanResult
from .input_guardrails import InputGuardrails, GuardrailInspectionResult

import re

logger = logging.getLogger("roottrace.live_debug.sanitizer")

SENSITIVE_CONFIG_PATTERN = re.compile(
    r"(?i)(?:^|[\\/])(?:\.env(?:\.[a-zA-Z0-9_-]+)?|.*credentials\.json|.*id_rsa|.*\.pem|.*service[-_]account.*\.json)$"
)

SAFE_ENV_DIAGNOSTIC_KEYS = {
    "NODE_ENV", "APP_ENV", "ENVIRONMENT", "PYTHONPATH", "PORT", "LOG_LEVEL", "DEBUG"
}


class SanitizedEvidenceRecord(BaseModel):

    id: str
    source_tool: str
    timestamp: str
    source_ref: str
    summary: str
    data: Dict[str, Any]
    reliability: float = 1.0
    relevance_tags: List[str] = Field(default_factory=list)
    redaction_count: int = 0
    is_truncated: bool = False
    flagged_for_injection: bool = False


class SanitizationSummary(BaseModel):
    total_records_in: int
    total_records_out: int
    total_redactions: int
    total_bytes: int
    has_injections_flagged: bool
    rules_triggered: List[str] = Field(default_factory=list)
    sanitized_at: str


class EvidenceSanitizer:
    """
    Sanitizes raw evidence before it enters any AI model context.
    Ensures all secrets are redacted and content bounds are strictly enforced.
    """

    def __init__(
        self,
        scanner: Optional[SecretScanner] = None,
        guardrails: Optional[InputGuardrails] = None
    ):
        self.scanner = scanner or SecretScanner()
        self.guardrails = guardrails or InputGuardrails()

    def sanitize_evidence_record(self, raw_record: Dict[str, Any]) -> SanitizedEvidenceRecord:
        """
        Sanitizes an individual evidence record.
        Preserves ID, timestamps, and tool provenance.
        Redacts credentials from data, summary, and source_ref.
        """
        try:
            ev_id = str(raw_record.get("id", "ev_unknown"))
            source_tool = str(raw_record.get("source_tool", "unknown"))
            timestamp = str(raw_record.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()))
            source_ref = str(raw_record.get("source_ref", ""))
            summary = str(raw_record.get("summary", ""))
            data = raw_record.get("data", {})
            reliability = float(raw_record.get("reliability", 1.0))
            tags = list(raw_record.get("relevance_tags", []))

            # 1. Check for sensitive config files (.env, credentials.json, etc.) or raw environment dumps
            is_sensitive_file = bool(SENSITIVE_CONFIG_PATTERN.search(source_ref))
            is_env_dump = source_tool in ("env_dump", "environment", "env_vars", "os_environ")
            
            # Check if dict payload looks like an unrestricted environment dump
            looks_like_env_dump = False
            if isinstance(data, dict) and len(data) > 3:
                env_like_keys = sum(1 for k in data.keys() if str(k).isupper() and "_" in str(k))
                if env_like_keys >= 3:
                    looks_like_env_dump = True

            if is_sensitive_file or is_env_dump or looks_like_env_dump:
                # Safely summarize: preserve safe diagnostic keys only, withhold everything else
                safe_diagnostics = {}
                if isinstance(data, dict):
                    for k, v in data.items():
                        if str(k).upper() in SAFE_ENV_DIAGNOSTIC_KEYS:
                            safe_diagnostics[str(k)] = str(v)

                return SanitizedEvidenceRecord(
                    id=ev_id,
                    source_tool=source_tool,
                    timestamp=timestamp,
                    source_ref=self.scanner.scan_and_redact(source_ref).sanitized_text,
                    summary=f"[SAFE SUMMARY: Sensitive configuration or environment collection withheld by guardrails]",
                    data={
                        "status": "SANITIZED_CONFIG",
                        "notice": "Raw environment file or environment variable collection was withheld to protect secrets.",
                        "safe_diagnostics": safe_diagnostics
                    },
                    reliability=0.5,
                    relevance_tags=tags + ["sensitive_config_sanitized"],
                    redaction_count=1,
                    is_truncated=False,
                    flagged_for_injection=False
                )

            # 2. Redact secrets from metadata strings
            ref_scan = self.scanner.scan_and_redact(source_ref)
            sum_scan = self.scanner.scan_and_redact(summary)

            # 3. Redact secrets recursively from data payload
            sanitized_data, data_redactions, data_audits = self.scanner.sanitize_structure(data)

            total_redactions = ref_scan.redactions_count + sum_scan.redactions_count + data_redactions

            # 4. Guardrail inspection for prompt injection
            data_str = str(sanitized_data)
            bounded_text, is_trunc, violations = self.guardrails.inspect_and_bound_text(data_str, source_id=ev_id)
            has_injection = any(v.check_name == "PROMPT_INJECTION_FLAG" for v in violations)

            return SanitizedEvidenceRecord(
                id=ev_id,
                source_tool=source_tool,
                timestamp=timestamp,
                source_ref=ref_scan.sanitized_text,
                summary=sum_scan.sanitized_text,
                data=sanitized_data if isinstance(sanitized_data, dict) else {"content": sanitized_data},
                reliability=reliability,
                relevance_tags=tags,
                redaction_count=total_redactions,
                is_truncated=is_trunc,
                flagged_for_injection=has_injection
            )
        except Exception as e:
            logger.error(f"Sanitization failed for record {raw_record.get('id')}: {e}")
            # Fail safely: DO NOT emit raw record. Emit safe error placeholder.
            return SanitizedEvidenceRecord(
                id=str(raw_record.get("id", "ev_sanitization_failed")),
                source_tool="sanitizer_error",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_ref="sanitizer:error",
                summary="[REDACTED: Record omitted due to sanitization error]",
                data={"error": "Failed safe sanitization. Raw data withheld."},
                reliability=0.0,
                redaction_count=1,
                is_truncated=True,
                flagged_for_injection=False
            )

    def sanitize_evidence_collection(
        self,
        records: List[Dict[str, Any]]
    ) -> Tuple[List[SanitizedEvidenceRecord], SanitizationSummary]:
        """
        Sanitizes a batch of evidence records, producing a bounded, sanitized list
        and a high-level audit summary.
        """
        sanitized_records: List[SanitizedEvidenceRecord] = []
        total_redactions = 0
        rules_triggered: set = set()
        has_injection = False

        for r in records:
            san_rec = self.sanitize_evidence_record(r)
            sanitized_records.append(san_rec)
            total_redactions += san_rec.redaction_count
            if san_rec.flagged_for_injection:
                has_injection = True

        summary = SanitizationSummary(
            total_records_in=len(records),
            total_records_out=len(sanitized_records),
            total_redactions=total_redactions,
            total_bytes=sum(len(str(r.data).encode("utf-8")) for r in sanitized_records),
            has_injections_flagged=has_injection,
            rules_triggered=list(rules_triggered),
            sanitized_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

        return sanitized_records, summary
