"""
Server-side Authentication and Authorization Service for RootTrace.
Issues cryptographically random session tokens and enforces strict role-based access.
Credentials are NEVER hardcoded in source code or publicly enumerated.
"""
import datetime
import secrets
from typing import Dict, Optional, Set
from pydantic import BaseModel, Field
from fastapi import HTTPException, status


class UserPrincipal(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    is_active: bool = True


class SessionRecord(BaseModel):
    token: str
    principal: UserPrincipal
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    expires_at: datetime.datetime


# Organization Directory defining authorized SRE personnel and their verified roles
ORGANIZATION_DIRECTORY: Dict[str, Dict[str, str]] = {
    "lead_sre@company.com": {
        "user_id": "usr_sre_01",
        "name": "Lead SRE (Primary)",
        "role": "lead_sre"
    },
    "incident_commander@company.com": {
        "user_id": "usr_cmd_02",
        "name": "Incident Commander",
        "role": "incident_commander"
    },
    "oncall_sre@company.com": {
        "user_id": "usr_oncall_03",
        "name": "On-Call SRE",
        "role": "oncall_sre"
    },
    "staff_sre@company.com": {
        "user_id": "usr_staff_04",
        "name": "Staff SRE",
        "role": "staff_sre"
    },
    "intern_observer@company.com": {
        "user_id": "usr_intern_99",
        "name": "Junior SRE Intern",
        "role": "intern"
    }
}

AUTHORIZED_APPROVER_ROLES: Set[str] = {
    "incident_commander",
    "oncall_sre",
    "lead_sre",
    "staff_sre",
    "principal_sre"
}

# In-memory ephemeral active session registry: token -> SessionRecord
_ACTIVE_SESSIONS: Dict[str, SessionRecord] = {}


def create_authenticated_session(email: str, ttl_seconds: int = 3600) -> SessionRecord:
    """
    Authenticates an operator against the organization directory and issues
    a cryptographically secure random session token.
    Role is derived strictly from the directory and cannot be forged by the client.
    """
    clean_email = email.strip().lower()
    user_info = ORGANIZATION_DIRECTORY.get(clean_email)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: User '{email}' is not in the organization directory."
        )

    # Generate a cryptographically random, unguessable token
    token = secrets.token_urlsafe(32)
    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + datetime.timedelta(seconds=ttl_seconds)

    principal = UserPrincipal(
        user_id=user_info["user_id"],
        email=clean_email,
        name=user_info["name"],
        role=user_info["role"],
        is_active=True
    )

    record = SessionRecord(
        token=token,
        principal=principal,
        created_at=now,
        expires_at=expires
    )
    _ACTIVE_SESSIONS[token] = record
    return record


def authenticate_and_authorize_approver(
    auth_token: Optional[str] = None,
    client_claimed_approver: Optional[str] = None,
    client_claimed_role: Optional[str] = None
) -> UserPrincipal:
    """
    Validates a session token.
    Strictly derives identity and role from the active server session.
    Rejects missing, expired, or invalid tokens with 401 Unauthorized.
    Rejects unauthorized roles with 403 Forbidden.
    Rejects client attempts to spoof identity or elevate roles with 403 Forbidden.
    """
    if not auth_token or not auth_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing or empty 'auth_token'. Provide a verified session token."
        )

    token_clean = auth_token.strip()
    if token_clean.lower().startswith("bearer "):
        token_clean = token_clean[7:].strip()

    session = _ACTIVE_SESSIONS.get(token_clean)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid or unrecognized approval session token."
        )

    # Check session expiration
    now = datetime.datetime.now(datetime.timezone.utc)
    if now > session.expires_at:
        _ACTIVE_SESSIONS.pop(token_clean, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Session token has expired. Please re-authenticate."
        )

    principal = session.principal
    if not principal.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User principal '{principal.email}' is inactive."
        )

    # Enforce role-based authorization policy
    normalized_role = principal.role.strip().lower().replace(" ", "_")
    if normalized_role not in AUTHORIZED_APPROVER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Principal '{principal.email}' with role '{principal.role}' is not authorized to approve consequential remediation actions. Authorized roles: {sorted(list(AUTHORIZED_APPROVER_ROLES))}"
        )

    # Defend against spoofing
    if client_claimed_approver and client_claimed_approver.strip():
        claimed_clean = client_claimed_approver.strip().lower()
        if claimed_clean not in (principal.email.lower(), principal.user_id.lower()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Identity mismatch: Session belongs to '{principal.email}', cannot approve as '{client_claimed_approver}'."
            )

    if client_claimed_role and client_claimed_role.strip():
        claimed_role_norm = client_claimed_role.strip().lower().replace(" ", "_")
        if claimed_role_norm != normalized_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role mismatch: Session grants role '{principal.role}', cannot approve as '{client_claimed_role}'."
            )

    return principal


def reset_auth_sessions():
    """Clear all active sessions (used during test teardown)."""
    _ACTIVE_SESSIONS.clear()
