"""
Centralized Secret Scanner and Data Redaction Engine for RootTrace.
Scans model-bound logs, tracebacks, git diffs, environment values, and evidence records
for sensitive credentials and secrets, applying deterministic redaction.

Never writes raw secret values to logs, audit records, or persistent files.
"""
import re
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SecretRule:
    rule_id: str
    name: str
    pattern: re.Pattern
    description: str


# Compiled, bounded regex patterns designed to prevent catastrophic backtracking
COMPILED_RULES: List[SecretRule] = [
    # 1. Private Keys
    SecretRule(
        rule_id="SEC_PRIV_KEY",
        name="Private Key Block",
        pattern=re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
        ),
        description="PEM/OpenSSH private key block"
    ),
    # 2. OpenAI / Anthropic / AI API Keys
    SecretRule(
        rule_id="SEC_AI_KEY",
        name="AI Provider API Key",
        pattern=re.compile(r"\b(?:sk-[a-zA-Z0-9_-]{20,}|sk-ant-[a-zA-Z0-9_-]{20,}|AIza[0-9A-Za-z-_]{35})\b"),
        description="OpenAI, Anthropic, or Google AI API key"
    ),
    # 3. GitHub Personal Access Tokens
    SecretRule(
        rule_id="SEC_GH_TOKEN",
        name="GitHub Personal Access Token",
        pattern=re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"),
        description="GitHub fine-grained or classic token"
    ),
    # 4. AWS Access Key ID
    SecretRule(
        rule_id="SEC_AWS_KEY",
        name="AWS Access Key ID",
        pattern=re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        description="AWS Access Key ID"
    ),
    # 5. Database Connection URIs with Passwords
    SecretRule(
        rule_id="SEC_DB_URI",
        name="Database Connection URI with Credentials",
        pattern=re.compile(
            r"(?i)\b(?:postgres|postgresql|mysql|mongodb|redis|amqp)://(?:[^:\s/@]*):([^@\s/]+)@[\w.-]+(?::\d+)?(?:/[^\s]*)?"
        ),
        description="Database connection URI containing plaintext password"
    ),
    # 6. Bearer Authorization Headers / Tokens
    SecretRule(
        rule_id="SEC_BEARER",
        name="Authorization Bearer Token",
        pattern=re.compile(r"(?i)\bBearer\s+([a-zA-Z0-9_\-\.]{20,})\b"),
        description="HTTP Bearer authentication token"
    ),
    # 7. Explicit Password / Secret Key Assignments in Config or Code
    SecretRule(
        rule_id="SEC_ASSIGNMENT",
        name="Credential Assignment",
        pattern=re.compile(
            r"""(?ix)
            \b(api[_-]?key|access[_-]?token|secret[_-]?key|client[_-]?secret|password|passwd|pwd)
            \s*[:=]\s*
            (['"])([^\r\n'"]{6,})\2
            """
        ),
        description="Explicit secret or password assignment in configuration, JSON, or code"
    )
]


@dataclass
class RedactionAuditRecord:
    rule_id: str
    rule_name: str
    match_count: int


@dataclass
class ScanResult:
    sanitized_text: str
    redactions_count: int
    rule_matches: List[RedactionAuditRecord] = field(default_factory=list)

    @property
    def has_redactions(self) -> bool:
        return self.redactions_count > 0


class SecretScanner:
    """
    Scans and sanitizes strings, dictionaries, or lists.
    Guarantees deterministic, idempotent redaction without storing or logging matched secret values.
    """

    def __init__(self, custom_rules: Optional[List[SecretRule]] = None):
        self.rules = list(COMPILED_RULES)
        if custom_rules:
            self.rules.extend(custom_rules)

    def scan_and_redact(self, text: str) -> ScanResult:
        """
        Scans a text string and returns a ScanResult containing sanitized text and audit metadata.
        Raw secret values are completely discarded and never recorded.
        """
        if not text or not isinstance(text, str):
            return ScanResult(sanitized_text=text or "", redactions_count=0)

        sanitized = text
        total_redactions = 0
        rule_audits: List[RedactionAuditRecord] = []

        for rule in self.rules:
            matches_count = 0

            # Special case for DB URIs and Assignments where we want to redact only the secret portion
            if rule.rule_id == "SEC_DB_URI":
                def db_replacer(m: re.Match) -> str:
                    nonlocal matches_count
                    matches_count += 1
                    # Redact the password group (group 1)
                    full_match = m.group(0)
                    pwd = m.group(1)
                    return full_match.replace(f":{pwd}@", f":[REDACTED:{rule.rule_id}]@")

                sanitized, n = rule.pattern.subn(db_replacer, sanitized)
                if n > 0:
                    total_redactions += n
                    rule_audits.append(RedactionAuditRecord(rule.rule_id, rule.name, n))

            elif rule.rule_id == "SEC_BEARER":
                def bearer_replacer(m: re.Match) -> str:
                    nonlocal matches_count
                    matches_count += 1
                    return f"Bearer [REDACTED:{rule.rule_id}]"

                sanitized, n = rule.pattern.subn(bearer_replacer, sanitized)
                if n > 0:
                    total_redactions += n
                    rule_audits.append(RedactionAuditRecord(rule.rule_id, rule.name, n))

            elif rule.rule_id == "SEC_ASSIGNMENT":
                def assign_replacer(m: re.Match) -> str:
                    nonlocal matches_count
                    matches_count += 1
                    key_name = m.group(1)
                    quote = m.group(2)
                    return f"{key_name}={quote}[REDACTED:{rule.rule_id}]{quote}"

                sanitized, n = rule.pattern.subn(assign_replacer, sanitized)
                if n > 0:
                    total_redactions += n
                    rule_audits.append(RedactionAuditRecord(rule.rule_id, rule.name, n))

            else:
                # Default whole-match redaction (e.g. API keys, private keys)
                def general_replacer(m: re.Match) -> str:
                    nonlocal matches_count
                    matches_count += 1
                    return f"[REDACTED:{rule.rule_id}]"

                sanitized, n = rule.pattern.subn(general_replacer, sanitized)
                if n > 0:
                    total_redactions += n
                    rule_audits.append(RedactionAuditRecord(rule.rule_id, rule.name, n))

        return ScanResult(
            sanitized_text=sanitized,
            redactions_count=total_redactions,
            rule_matches=rule_audits
        )

    def sanitize_structure(self, obj: Any) -> Tuple[Any, int, List[RedactionAuditRecord]]:
        """
        Recursively sanitizes nested dictionaries, lists, and primitives.
        """
        if isinstance(obj, str):
            res = self.scan_and_redact(obj)
            return res.sanitized_text, res.redactions_count, res.rule_matches

        elif isinstance(obj, dict):
            sanitized_dict = {}
            total_count = 0
            all_audits = []
            for k, v in obj.items():
                san_k, k_count, k_audits = self.sanitize_structure(k)
                san_v, v_count, v_audits = self.sanitize_structure(v)
                sanitized_dict[san_k] = san_v
                total_count += k_count + v_count
                all_audits.extend(k_audits + v_audits)
            return sanitized_dict, total_count, all_audits

        elif isinstance(obj, list):
            sanitized_list = []
            total_count = 0
            all_audits = []
            for item in obj:
                san_item, i_count, i_audits = self.sanitize_structure(item)
                sanitized_list.append(san_item)
                total_count += i_count
                all_audits.extend(i_audits)
            return sanitized_list, total_count, all_audits

        return obj, 0, []
