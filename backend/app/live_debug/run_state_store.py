"""
Atomic Persistent Run State Store for RootTrace Live.
Guarantees multi-process safe, transactional state transitions for patch approvals,
preventing race conditions, duplicate applications, replay attacks, and state ambiguity
across process restarts or multi-worker uvicorn deployments.
"""
import os
import sqlite3
import datetime
from typing import Dict, Any, Optional, Tuple

DB_PATH = os.getenv("ROOTTRACE_SESSION_DB", os.path.join(os.path.dirname(__file__), "..", "safety", "sessions.db"))


class LiveRunStateStore:
    """
    SQLite-backed transactional store for investigation runs and approvals.
    Uses immediate transactions and row-level checks to prevent concurrent duplicate applications.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS live_investigation_runs (
                    run_id TEXT PRIMARY KEY,
                    workspace_dir TEXT NOT NULL,
                    patch_hash TEXT NOT NULL,
                    diff_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    approver TEXT,
                    approver_role TEXT,
                    rejection_reason TEXT,
                    test_summary TEXT,
                    recovery_verified INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON live_investigation_runs(status);")
            conn.commit()

    def create_run(
        self,
        run_id: str,
        workspace_dir: str,
        patch_hash: str,
        diff_text: str,
        status: str = "PENDING"
    ):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO live_investigation_runs
                (run_id, workspace_dir, patch_hash, diff_text, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (run_id, workspace_dir, patch_hash, diff_text, status, now, now))
            conn.commit()

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM live_investigation_runs WHERE run_id = ?;", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def transition_to_applying(
        self,
        run_id: str,
        expected_patch_hash: str,
        expected_workspace: str,
        approver: str,
        approver_role: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Atomically checks preconditions and transitions run to APPLYING inside a single transaction.
        Rejects concurrent approvals, stale/tampered hashes, or workspace mismatches.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute("SELECT * FROM live_investigation_runs WHERE run_id = ?;", (run_id,))
            row = cursor.fetchone()
            if not row:
                conn.commit()
                return False, "NOT_FOUND", None

            run_dict = dict(row)
            current_status = run_dict.get("status")

            # 1. State check
            if current_status in ("APPLYING", "APPLIED", "VALIDATING", "VERIFIED"):
                conn.commit()
                return False, f"CONFLICT_ALREADY_IN_PROGRESS:{current_status}", run_dict

            if current_status == "REJECTED":
                conn.commit()
                return False, "CONFLICT_ALREADY_REJECTED", run_dict

            # 2. Patch hash binding verification
            if run_dict.get("patch_hash") != expected_patch_hash:
                conn.commit()
                return False, "HASH_MISMATCH", run_dict

            # 3. Workspace binding verification (cross-platform canonical comparison)
            ws_stored = os.path.normcase(os.path.realpath(run_dict.get("workspace_dir", "")))
            ws_expected = os.path.normcase(os.path.realpath(expected_workspace))
            if ws_stored != ws_expected:
                conn.commit()
                return False, "WORKSPACE_MISMATCH", run_dict

            # 4. Atomic update to APPLYING
            conn.execute("""
                UPDATE live_investigation_runs
                SET status = 'APPLYING', approver = ?, approver_role = ?, updated_at = ?
                WHERE run_id = ? AND status = 'PENDING';
            """, (approver, approver_role, now, run_id))
            conn.commit()
            return True, None, run_dict
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_status(
        self,
        run_id: str,
        new_status: str,
        test_summary: Optional[str] = None,
        recovery_verified: Optional[bool] = None
    ):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE live_investigation_runs
                SET status = ?,
                    test_summary = COALESCE(?, test_summary),
                    recovery_verified = COALESCE(?, recovery_verified),
                    updated_at = ?
                WHERE run_id = ?;
            """, (new_status, test_summary, 1 if recovery_verified else (0 if recovery_verified is False else None), now, run_id))
            conn.commit()

    def reject_run(self, run_id: str, reason: str) -> Tuple[bool, Optional[str]]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute("SELECT status FROM live_investigation_runs WHERE run_id = ?;", (run_id,))
            row = cursor.fetchone()
            if not row:
                conn.commit()
                return False, "NOT_FOUND"

            current_status = row["status"]
            if current_status in ("APPLYING", "APPLIED", "VALIDATING", "VERIFIED"):
                conn.commit()
                return False, f"CONFLICT:{current_status}"

            conn.execute("""
                UPDATE live_investigation_runs
                SET status = 'REJECTED', rejection_reason = ?, updated_at = ?
                WHERE run_id = ?;
            """, (reason, now, run_id))
            conn.commit()
            return True, None
        finally:
            conn.close()

    def recover_interrupted_runs(self, workspace_mgr: Any) -> int:
        """
        Detects any runs that were left in APPLYING or VALIDATING state due to unexpected
        process termination, marks them INTERRUPTED, and rolls back their workspace.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        recovered_count = 0
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT run_id, workspace_dir FROM live_investigation_runs
                WHERE status IN ('APPLYING', 'VALIDATING');
            """)
            interrupted = cursor.fetchall()
            for row in interrupted:
                rid = row["run_id"]
                ws = row["workspace_dir"]
                if workspace_mgr and os.path.exists(ws):
                    try:
                        workspace_mgr.rollback(ws, "pre_patch")
                    except Exception:
                        pass
                conn.execute("""
                    UPDATE live_investigation_runs
                    SET status = 'INTERRUPTED', rejection_reason = 'Process interrupted during application or validation', updated_at = ?
                    WHERE run_id = ?;
                """, (now, rid))
                recovered_count += 1
            conn.commit()
        return recovered_count
