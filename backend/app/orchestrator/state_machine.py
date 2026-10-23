"""
Deterministic State Machine for RootTrace Investigation Orchestrator.
Defines strict legal phase transitions and validation.
"""
from typing import Set, Dict
from ..models.domain import InvestigationPhase


VALID_TRANSITIONS: Dict[InvestigationPhase, Set[InvestigationPhase]] = {
    InvestigationPhase.TRIGGERED: {
        InvestigationPhase.OBSERVING,
        InvestigationPhase.PAUSED,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.OBSERVING: {
        InvestigationPhase.COLLECTING_INITIAL_EVIDENCE,
        InvestigationPhase.PAUSED,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.COLLECTING_INITIAL_EVIDENCE: {
        InvestigationPhase.BUILDING_TIMELINE,
        InvestigationPhase.PAUSED,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.BUILDING_TIMELINE: {
        InvestigationPhase.HYPOTHESIS_GENERATION,
        InvestigationPhase.PAUSED,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.HYPOTHESIS_GENERATION: {
        InvestigationPhase.INVESTIGATING,
        InvestigationPhase.PAUSED,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.INVESTIGATING: {
        InvestigationPhase.INVESTIGATING,  # Loop while gathering evidence
        InvestigationPhase.CRITIQUE,
        InvestigationPhase.PAUSED,
        InvestigationPhase.ESCALATED,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.CRITIQUE: {
        InvestigationPhase.VERIFYING,
        InvestigationPhase.INVESTIGATING,  # Return for more evidence if critique reveals gaps
        InvestigationPhase.PAUSED,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.VERIFYING: {
        InvestigationPhase.AWAITING_APPROVAL,
        InvestigationPhase.REMEDIATING,     # Only if auto-permitted (read-only)
        InvestigationPhase.INVESTIGATING,  # If unverified, loop back
        InvestigationPhase.ESCALATED,
        InvestigationPhase.PAUSED,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.AWAITING_APPROVAL: {
        InvestigationPhase.REMEDIATING,
        InvestigationPhase.INVESTIGATING,  # Operator requested more evidence
        InvestigationPhase.ESCALATED,
        InvestigationPhase.PAUSED,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.REMEDIATING: {
        InvestigationPhase.VERIFYING_RECOVERY,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.VERIFYING_RECOVERY: {
        InvestigationPhase.RESOLVED,
        InvestigationPhase.FAILED,
        InvestigationPhase.ESCALATED
    },
    InvestigationPhase.PAUSED: {
        InvestigationPhase.OBSERVING,
        InvestigationPhase.COLLECTING_INITIAL_EVIDENCE,
        InvestigationPhase.BUILDING_TIMELINE,
        InvestigationPhase.HYPOTHESIS_GENERATION,
        InvestigationPhase.INVESTIGATING,
        InvestigationPhase.CRITIQUE,
        InvestigationPhase.VERIFYING,
        InvestigationPhase.AWAITING_APPROVAL,
        InvestigationPhase.REMEDIATING,
        InvestigationPhase.VERIFYING_RECOVERY,
        InvestigationPhase.FAILED
    },
    InvestigationPhase.RESOLVED: set(),
    InvestigationPhase.FAILED: {InvestigationPhase.TRIGGERED},
    InvestigationPhase.ESCALATED: {InvestigationPhase.INVESTIGATING, InvestigationPhase.AWAITING_APPROVAL}
}


class InvestigationStateMachine:
    @staticmethod
    def can_transition(current: InvestigationPhase, target: InvestigationPhase) -> bool:
        allowed = VALID_TRANSITIONS.get(current, set())
        return target in allowed

    @staticmethod
    def validate_transition(current: InvestigationPhase, target: InvestigationPhase):
        if not InvestigationStateMachine.can_transition(current, target):
            raise ValueError(
                f"Illegal state transition from '{current.value}' to '{target.value}'. Allowed transitions: {[p.value for p in VALID_TRANSITIONS.get(current, set())]}"
            )
