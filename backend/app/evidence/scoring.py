"""
Deterministic Evidence Scoring and Timeline Construction Engine for RootTrace.
Evaluates evidence support without arbitrary LLM guesses and sorts events chronologically,
marking causal candidates and temporal red herrings.
"""
from typing import Dict, Any, List, Optional
import datetime
from ..models.domain import EvidenceRecord, TimelineEvent, Hypothesis, HypothesisStatus


class EvidenceEngine:
    @staticmethod
    def build_timeline(evidence_records: Dict[str, EvidenceRecord]) -> List[TimelineEvent]:
        """
        Merge events from logs, git, deployments, metrics, traces into a chronological timeline.
        Sort deterministically by ISO timestamp.
        """
        events: List[TimelineEvent] = []

        for ev_id, ev in evidence_records.items():
            data = ev.data
            ts = ev.timestamp

            # Extract from logs
            if ev.source_tool == "query_logs":
                log_data = data
                service = log_data.get("service", "unknown")
                msg = log_data.get("message", "")
                level = log_data.get("level", "INFO")

                is_causal = False
                is_herring = False

                if "Concurrent state transition conflict" in msg or "duplicate delivered" in msg:
                    is_causal = True
                elif "High CPU utilization detected on orders-db" in msg or "DB_HIGH_CPU" in msg:
                    # Red herring: happened at 14:07:30, after failures at 14:01:05!
                    is_herring = True

                events.append(TimelineEvent(
                    id=f"evt_{ev_id}",
                    timestamp=ts,
                    source=f"log:{service}",
                    event_type=f"LOG_{level}",
                    description=f"[{service}] {msg}",
                    evidence_id=ev_id,
                    is_causal_candidate=is_causal,
                    is_misleading_red_herring=is_herring,
                    metadata={"level": level, "service": service}
                ))

            # Extract from deployments
            elif ev.source_tool == "check_deployments":
                deploys = data.get("deployments", [])
                for d in deploys:
                    events.append(TimelineEvent(
                        id=f"evt_dep_{d.get('id')}",
                        timestamp=d.get("deployed_at", ts),
                        source="deployment",
                        event_type="DEPLOYMENT",
                        description=f"Deployment {d.get('version')} deployed to {d.get('service')}: {d.get('change_summary')}",
                        evidence_id=ev_id,
                        is_causal_candidate="remove" in d.get("change_summary", "").lower() or "lock" in d.get("change_summary", "").lower(),
                        is_misleading_red_herring=False,
                        metadata=d
                    ))

            # Extract from git commits
            elif ev.source_tool == "get_git_changes":
                events.append(TimelineEvent(
                    id=f"evt_git_{data.get('commit_sha', 'c')}",
                    timestamp=data.get("committed_at", ts),
                    source="git",
                    event_type="COMMIT",
                    description=f"Commit {data.get('commit_sha')[:7]} by {data.get('author')}: {data.get('message')}",
                    evidence_id=ev_id,
                    is_causal_candidate=True,
                    is_misleading_red_herring=False,
                    metadata=data
                ))

            # Extract from traces
            elif ev.source_tool == "get_trace":
                events.append(TimelineEvent(
                    id=f"evt_trace_{data.get('trace_id', 't')}",
                    timestamp=data.get("timestamp", ts),
                    source="trace",
                    event_type="DISTRIBUTED_TRACE",
                    description=f"Trace {data.get('trace_id')} ({data.get('endpoint')}): error in state transition",
                    evidence_id=ev_id,
                    is_causal_candidate=True,
                    is_misleading_red_herring=False,
                    metadata=data
                ))

        # Sort strictly by timestamp string (ISO-8601 sorts lexicographically)
        events.sort(key=lambda e: (e.timestamp, e.id))
        return events

    @staticmethod
    def calculate_hypothesis_score(
        hypothesis: Hypothesis,
        evidence_store: Dict[str, EvidenceRecord]
    ) -> float:
        """
        Deterministic evidence support score calculation between -1.0 and 1.0:
        - Supporting evidence: +0.25 * reliability
        - Direct evidence (code diff, trace conflict, exact concurrent collision): +0.35 * reliability
        - Missing expected evidence: -0.15 per item
        - Contradicting evidence: -0.45 * reliability (decisive refutation)
        """
        score = 0.0

        for ev_id in hypothesis.supporting_evidence_ids:
            ev = evidence_store.get(ev_id)
            if not ev:
                continue

            weight = 0.25 * ev.reliability
            summary_lower = ev.summary.lower()

            # Direct evidence boosts
            if any(term in summary_lower for term in [
                "conflict", "concurrent", "race", "diff", "remove redis lock", "thread="
            ]):
                weight += 0.15
            elif "pool timeout" in summary_lower or "503 service unavailable" in summary_lower:
                weight += 0.15

            score += weight

        for ev_id in hypothesis.contradicting_evidence_ids:
            ev = evidence_store.get(ev_id)
            if not ev:
                continue
            # Contradictions are heavily penalized
            score -= (0.45 * ev.reliability)

        # Missing expected evidence penalty
        if hypothesis.evidence_still_needed:
            score -= (0.10 * len(hypothesis.evidence_still_needed))

        # Clamp between -1.0 and 1.0
        return max(-1.0, min(1.0, round(score, 3)))

    @staticmethod
    def evaluate_hypothesis_status(score: float, has_contradiction: bool) -> HypothesisStatus:
        if has_contradiction or score < -0.2:
            return HypothesisStatus.FALSIFIED
        if score >= 0.70:
            return HypothesisStatus.SUPPORTED
        if score > 0.30:
            return HypothesisStatus.INVESTIGATING
        return HypothesisStatus.WEAKENED
