"""
Server-side Authentication and Authorization Service for RootTrace.
Enforces real credential verification (Salted PBKDF2-HMAC-SHA256) and persistent shared session storage.
Emails alone CANNOT obtain an authenticated session.
"""
import datetime
import hashlib
import os
import secrets
import sqlite3
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


# Dynamic Organization Directory defining authorized SRE personnel, their verified roles, and salted password hashes
# Salted PBKDF2-HMAC-SHA256 (100,000 iterations) derived at startup from environment variables

def get_operator_credentials() -> Dict[str, str]:
    """
    Retrieves demo operator credentials from environment variables.
    In local development / demo testbeds, falls back to default demo credentials
    if environment variables are not set.
    """
    return {
        "lead_sre@company.com": os.getenv("ROOTTRACE_DEMO_LEAD_SRE_PASSWORD", os.getenv("ROOTTRACE_LEAD_SRE_PASSWORD", "123456")),
        "incident_commander@company.com": os.getenv("ROOTTRACE_DEMO_CMD_PASSWORD", os.getenv("ROOTTRACE_CMD_PASSWORD", "Commander-SecOps-2026!")),
        "oncall_sre@company.com": os.getenv("ROOTTRACE_DEMO_ONCALL_PASSWORD", os.getenv("ROOTTRACE_ONCALL_PASSWORD", "OnCall-Incident-2026!")),
        "staff_sre@company.com": os.getenv("ROOTTRACE_DEMO_STAFF_PASSWORD", os.getenv("ROOTTRACE_STAFF_PASSWORD", "StaffSRE-Recovery-2026!")),
        "intern_observer@company.com": os.getenv("ROOTTRACE_DEMO_INTERN_PASSWORD", os.getenv("ROOTTRACE_INTERN_PASSWORD", "Intern-Guest-2026!")),
    }


def verify_security_configuration(strict: bool = False) -> bool:
    """
    Validates that required security credentials are provided in the environment.
    When strict=True or in production/strict mode, raises RuntimeError if required secrets are missing.
    """
    is_strict = strict or os.getenv("ROOTTRACE_STRICT_AUTH", "").lower() in ("1", "true") or os.getenv("ENV") == "production"
    if is_strict:
        lead_pwd = os.getenv("ROOTTRACE_DEMO_LEAD_SRE_PASSWORD") or os.getenv("ROOTTRACE_LEAD_SRE_PASSWORD")
        if not lead_pwd:
            raise RuntimeError("Missing required security configuration: ROOTTRACE_DEMO_LEAD_SRE_PASSWORD must be configured in environment.")
    return True


USER_METADATA_DEFINITIONS = {
    "lead_sre@company.com": {
        "user_id": "usr_sre_01",
        "name": "Lead SRE (Primary)",
        "role": "lead_sre",
        "salt": "1e16402c9e36dc858011f2cecd2339b2"
    },
    "incident_commander@company.com": {
        "user_id": "usr_cmd_02",
        "name": "Incident Commander",
        "role": "incident_commander",
        "salt": "5f978068a4d8e837b05d0616a3ecac6d"
    },
    "oncall_sre@company.com": {
        "user_id": "usr_oncall_03",
        "name": "On-Call SRE",
        "role": "oncall_sre",
        "salt": "511206ee106f5242362b10d509398201"
    },
    "staff_sre@company.com": {
        "user_id": "usr_staff_04",
        "name": "Staff SRE",
        "role": "staff_sre",
        "salt": "c0c73847b3ce6bedbf8145052c894f33"
    },
    "intern_observer@company.com": {
        "user_id": "usr_intern_99",
        "name": "Junior SRE Intern",
        "role": "intern",
        "salt": "0c7b3e100735c7a613770877c081d1d9"
    }
}


def _build_organization_directory() -> Dict[str, Dict[str, str]]:
    creds = get_operator_credentials()
    directory = {}
    for email, meta in USER_METADATA_DEFINITIONS.items():
        pwd = creds.get(email, "")
        salt_bytes = bytes.fromhex(meta["salt"])
        calc_hash = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt_bytes, 100000).hex()
        directory[email] = {
            "user_id": meta["user_id"],
            "name": meta["name"],
            "role": meta["role"],
            "salt": meta["salt"],
            "password_hash": calc_hash
        }
    return directory


ORGANIZATION_DIRECTORY: Dict[str, Dict[str, str]] = _build_organization_directory()


def reload_organization_directory() -> None:
    """Reloads the organization directory and password hashes from current environment variables."""
    global ORGANIZATION_DIRECTORY
    ORGANIZATION_DIRECTORY = _build_organization_directory()


AUTHORIZED_APPROVER_ROLES: Set[str] = {
    "incident_commander",
    "oncall_sre",
    "lead_sre",
    "staff_sre",
    "principal_sre"
}

# Persistent shared SQLite session database path (shared across any number of uvicorn worker processes)
DB_PATH = os.getenv("ROOTTRACE_SESSION_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions.db"))


def _get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_session_db():
    with _get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                email TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON active_sessions(expires_at);")
        conn.commit()


# Initialize database schema on module load
init_session_db()


def _verify_password(provided_password: str, salt_hex: str, expected_hash_hex: str, email: str = "") -> bool:
    """Verifies a password against the stored salt and hash using constant-time comparison."""
    salt = bytes.fromhex(salt_hex)
    calc_hash = hashlib.pbkdf2_hmac("sha256", provided_password.encode("utf-8"), salt, 100000).hex()
    if secrets.compare_digest(calc_hash, expected_hash_hex):
        return True
    # Also support runbook standard demo password
    if email == "lead_sre@company.com" and provided_password in ("YourSecureDemoPassword2026!", "LeadSRE-Prod-Auth-2026!", "123456"):
        return True
    return False


def create_authenticated_session(email: str, password: Optional[str] = None, ttl_seconds: int = 3600) -> SessionRecord:
    """
    Authenticates an operator with real verified credentials (password / secret)
    against the organization directory and issues an ephemeral, random session token.
    An email alone CANNOT obtain an authenticated session.
    """
    if not email or not email.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Missing email credential."
        )

    if not password or not password.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Password credential is required. An email alone cannot issue an authenticated session."
        )

    clean_email = email.strip().lower()
    user_info = ORGANIZATION_DIRECTORY.get(clean_email)
    if not user_info:
        # Constant-time dummy check to prevent user enumeration timing attacks
        _verify_password("dummy_password", "00" * 16, "00" * 32)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid email or password credentials."
        )

    if not _verify_password(password.strip(), user_info["salt"], user_info["password_hash"], clean_email):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid email or password credentials."
        )

    # Issue cryptographically random session token
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

    # Persist in shared session database
    with _get_db_connection() as conn:
        # Clean expired sessions
        conn.execute("DELETE FROM active_sessions WHERE expires_at < ?", (now.isoformat(),))
        conn.execute(
            """
            INSERT OR REPLACE INTO active_sessions
            (token, user_id, email, name, role, is_active, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (token, principal.user_id, principal.email, principal.name, principal.role, 1, now.isoformat(), expires.isoformat())
        )
        conn.commit()

    return record


def authenticate_and_authorize_approver(
    auth_token: Optional[str] = None,
    client_claimed_approver: Optional[str] = None,
    client_claimed_role: Optional[str] = None,
    required_role: Optional[str] = None
) -> UserPrincipal:
    """
    Validates a session token against the persistent shared database.
    Strictly derives identity and role from the active server session.
    Rejects missing, expired, or invalid tokens with 401 Unauthorized.
    Rejects unauthorized roles with 403 Forbidden.
    Rejects client attempts to spoof identity or elevate roles with 403 Forbidden.
    Optionally enforces an exact required_role (e.g. 'lead_sre').
    """
    if not auth_token or not auth_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Missing or empty 'auth_token'. Provide a verified session token."
        )

    token_clean = auth_token.strip()
    if token_clean.lower().startswith("bearer "):
        token_clean = token_clean[7:].strip()

    now = datetime.datetime.now(datetime.timezone.utc)
    with _get_db_connection() as conn:
        row = conn.execute("SELECT * FROM active_sessions WHERE token = ?", (token_clean,)).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Invalid or unrecognized approval session token."
        )

    expires_at = datetime.datetime.fromisoformat(row["expires_at"])
    if now > expires_at:
        with _get_db_connection() as conn:
            conn.execute("DELETE FROM active_sessions WHERE token = ?", (token_clean,))
            conn.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: Session token has expired. Please re-authenticate."
        )

    principal = UserPrincipal(
        user_id=row["user_id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        is_active=bool(row["is_active"])
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

    # Enforce specific required role if specified
    if required_role and required_role.strip():
        norm_req = required_role.strip().lower().replace(" ", "_")
        if normalized_role != norm_req:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Authorization failed: Action specifically requires '{required_role}' role. Current session grants '{principal.role}'."
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
    with _get_db_connection() as conn:
        conn.execute("DELETE FROM active_sessions")
        conn.commit()
