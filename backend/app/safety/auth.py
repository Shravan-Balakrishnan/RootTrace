"""
Server-side Authentication and Authorization Service for RootTrace.
Derives approver identity and role strictly from verified server-side tokens and sessions.
Guarantees that clients cannot self-assign privileged roles.
"""
from typing import Dict, Optional, Set
from pydantic import BaseModel
from fastapi import HTTPException, status, Header


class UserPrincipal(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    is_active: bool = True


# Pre-provisioned verified enterprise credentials / session tokens
VERIFIED_PRINCIPALS: Dict[str, UserPrincipal] = {
    "sre_token_lead": UserPrincipal(
        user_id="usr_lead_01",
        email="lead_sre@company.com",
        name="Lead SRE (Primary)",
        role="lead_sre"
    ),
    "sre_token_commander": UserPrincipal(
        user_id="usr_cmd_02",
        email="incident_commander@company.com",
        name="Incident Commander",
        role="incident_commander"
    ),
    "sre_token_oncall": UserPrincipal(
        user_id="usr_oncall_03",
        email="oncall_sre@company.com",
        name="On-Call SRE",
        role="oncall_sre"
    ),
    "sre_token_staff": UserPrincipal(
        user_id="usr_staff_04",
        email="staff_sre@company.com",
        name="Staff SRE",
        role="staff_sre"
    ),
    "guest_token_unauth": UserPrincipal(
        user_id="usr_intern_99",
        email="intern_observer@company.com",
        name="Guest Intern (Read-Only)",
        role="intern"
    )
}

AUTHORIZED_APPROVER_ROLES: Set[str] = {
    "incident_commander",
    "oncall_sre",
    "lead_sre",
    "staff_sre",
    "principal_sre"
}


def authenticate_and_authorize_approver(
    auth_token: Optional[str] = None,
    client_claimed_approver: Optional[str] = None,
    client_claimed_role: Optional[str] = None
) -> UserPrincipal:
    """
    Authenticates the token against server session registry.
    Strictly derives identity and role from the server-verified principal.
    Rejects missing/invalid tokens with 401 Unauthorized.
    Rejects unauthorized roles with 403 Forbidden.
    Rejects client attempts to spoof identity or elevate privileges.
    """
    if not auth_token or not auth_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing or empty 'auth_token'. Provide a verified SRE session token."
        )

    token_clean = auth_token.strip()
    # Support 'Bearer <token>' prefix if passed
    if token_clean.lower().startswith("bearer "):
        token_clean = token_clean[7:].strip()

    principal = VERIFIED_PRINCIPALS.get(token_clean)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid or unrecognized approval token."
        )

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

    # Defend against spoofing: If the client passed an approver or role that doesn't match the token
    if client_claimed_approver and client_claimed_approver.strip():
        claimed_clean = client_claimed_approver.strip().lower()
        if claimed_clean not in (principal.email.lower(), principal.user_id.lower()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Identity mismatch: Token belongs to '{principal.email}', cannot approve as '{client_claimed_approver}'."
            )

    if client_claimed_role and client_claimed_role.strip():
        claimed_role_norm = client_claimed_role.strip().lower().replace(" ", "_")
        if claimed_role_norm != normalized_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role mismatch: Token grants role '{principal.role}', cannot approve as '{client_claimed_role}'."
            )

    return principal
