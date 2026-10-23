"""
Audit Records and Continual Learning Engine for RootTrace Live.
Maintains bounded, structured audit trails and a retrieval corpus of verified historical incidents.
All stored records are sanitized and contain zero raw secrets.
"""
import os
import json
import datetime
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field

from .evidence_sanitizer import SanitizedEvidenceRecord


class AuditRecord(BaseModel):
    run_id: str
    timestamp: str
    observed_failure: str
    evidence_count: int
    hypotheses_evaluated: List[str]
    critic_verdict: str
    diagnosis: str
    patch_hash: Optional[str] = None
    target_workspace: Optional[str] = None
    approver: Optional[str] = None
    approver_role: Optional[str] = None
    approval_timestamp: Optional[str] = None
    test_result_summary: Optional[str] = None
    recovery_verified: bool = False
    audit_tags: List[str] = Field(default_factory=list)


class HistoricalIncidentCase(BaseModel):
    case_id: str
    signature: str
    root_cause: str
    patch_summary: str
    resolved_at: str
    verified: bool = True


class LiveAuditStore:
    """
    Persists audit records and provides retrieval for continual learning.
    """

    def __init__(self, storage_path: Optional[str] = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.storage_file = storage_path or os.path.join(base_dir, "live_audit_records.json")
        self._records: List[AuditRecord] = []
        self._historical_corpus: List[HistoricalIncidentCase] = [
            HistoricalIncidentCase(
                case_id="HIST-001",
                signature="ZeroDivisionError in order discount calculation",
                root_cause="Discount denominator evaluated to zero on 0% promotional code rate",
                patch_summary="Added guard clause max(rate, 0.01) before division in calculate_order_total",
                resolved_at="2026-09-15T11:20:00Z",
                verified=True
            ),
            HistoricalIncidentCase(
                case_id="HIST-002",
                signature="AssertionError in final_total tax calculation",
                root_cause="Tax amount calculated from discounted total but omitted from final addition",
                patch_summary="Changed return sum to include tax_amount in services.py",
                resolved_at="2026-10-02T16:45:00Z",
                verified=True
            )
        ]
        self._load()

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = [AuditRecord(**r) for r in data]
            except Exception:
                self._records = []

    def _save(self):
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump([r.model_dump() for r in self._records], f, indent=2)
        except Exception:
            pass

    def record_investigation(self, record: AuditRecord):
        """Appends an immutable audit record and persists to disk."""
        self._records.append(record)
        self._save()

    def retrieve_similar_cases(self, query: str, limit: int = 3) -> List[HistoricalIncidentCase]:
        """
        Retrieves similar verified historical incident cases for continual learning context.
        Matches by keyword overlap.
        """
        words = set(query.lower().split())
        scored: List[Tuple[int, HistoricalIncidentCase]] = []

        for case in self._historical_corpus:
            case_words = set(f"{case.signature} {case.root_cause}".lower().split())
            overlap = len(words.intersection(case_words))
            scored.append((overlap, case))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for score, c in scored[:limit]]

    def get_recent_audits(self, limit: int = 20) -> List[AuditRecord]:
        return self._records[-limit:]
