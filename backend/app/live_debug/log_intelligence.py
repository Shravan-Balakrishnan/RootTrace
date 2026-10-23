"""
Drain3-based Log Intelligence and Template Mining Engine for RootTrace Live.
Extracts recurring structured log templates from raw telemetry streams, groups repeated patterns,
and produces provenance-aware evidence for incident diagnosis.
Supports graceful, explicit fallback to a deterministic normalizer when Drain3 is unavailable or fails.
"""
import re
import datetime
import logging
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("roottrace.live_debug.log_intelligence")

try:
    from drain3 import TemplateMiner
    from drain3.template_miner_config import TemplateMinerConfig
    from drain3.masking import MaskingInstruction
    DRAIN3_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as exc:
    DRAIN3_AVAILABLE = False
    logger.info("Drain3 package not available. Using deterministic fallback: %s", exc)


class LogTemplateRecord(BaseModel):
    template_id: str
    template_text: str
    occurrence_count: int
    first_seen: str
    last_seen: str
    sample_messages: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)
    parameters_extracted: List[Dict[str, Any]] = Field(default_factory=list)


class LogIntelligenceReport(BaseModel):
    implementation_used: str  # "drain3" or "deterministic_fallback"
    templates: List[LogTemplateRecord] = Field(default_factory=list)
    total_messages_processed: int = 0
    unique_templates_count: int = 0
    degraded_mode: bool = False
    status_message: str = "OK"
    extraction_errors: List[str] = Field(default_factory=list)


class LogIntelligenceMiner:
    """
    Mines recurring log templates from collected process logs and telemetry streams.
    Prefers Drain3 when available, with deterministic fallback for reliability and test repeatability.
    """

    def __init__(self, force_fallback: bool = False):
        self.force_fallback = force_fallback
        self.use_drain3 = DRAIN3_AVAILABLE and not force_fallback

    def mine_log_templates(
        self,
        log_lines: List[str],
        timestamps: Optional[List[str]] = None,
        source_ref: str = "live-lab:stdout_stderr"
    ) -> LogIntelligenceReport:
        """
        Processes a sequence of log messages and clusters them into templates.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if not log_lines:
            return LogIntelligenceReport(
                implementation_used="drain3" if self.use_drain3 else "deterministic_fallback",
                templates=[],
                total_messages_processed=0,
                unique_templates_count=0,
                degraded_mode=False,
                status_message="No log messages to process"
            )

        # Truncate and sanitize lines to avoid ReDoS or memory issues
        clean_lines: List[Tuple[str, str]] = []
        for i, line in enumerate(log_lines):
            ts = timestamps[i] if (timestamps and i < len(timestamps)) else now
            if not isinstance(line, str):
                line = str(line)
            # Bound line length to 500 KB chunk safe limit
            bounded_line = line[:1000].strip()
            if bounded_line:
                clean_lines.append((bounded_line, ts))

        if not clean_lines:
            return LogIntelligenceReport(
                implementation_used="drain3" if self.use_drain3 else "deterministic_fallback",
                templates=[],
                total_messages_processed=0,
                unique_templates_count=0,
                degraded_mode=False,
                status_message="Empty log lines after trimming"
            )

        # Attempt Drain3 mining if enabled
        if self.use_drain3:
            try:
                return self._mine_with_drain3(clean_lines, source_ref)
            except Exception as e:
                logger.warning("Drain3 execution failed (%s); falling back to deterministic normalizer.", e)
                fallback_report = self._mine_with_fallback(clean_lines, source_ref)
                fallback_report.degraded_mode = True
                fallback_report.extraction_errors.append(f"Drain3 runtime failure: {str(e)}")
                fallback_report.status_message = f"Degraded mode: Drain3 failed ({str(e)}), used deterministic fallback"
                return fallback_report

        # Deterministic fallback mode
        return self._mine_with_fallback(clean_lines, source_ref)

    def _build_drain3_miner(self) -> Any:
        """Creates an isolated, repeatable TemplateMiner instance with configured masking instructions."""
        config = TemplateMinerConfig()
        config.mask_prefix = "<"
        config.mask_suffix = ">"
        config.masking_instructions = [
            MaskingInstruction(r"((?<=[^A-Za-z0-9])|^)[\-\+]?\d+((?=[^A-Za-z0-9])|$)", "NUM"),
            MaskingInstruction(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", "UUID"),
            MaskingInstruction(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IP"),
            MaskingInstruction(r"\b0x[0-9a-fA-F]+\b", "HEX")
        ]
        return TemplateMiner(config=config)

    def _mine_with_drain3(
        self,
        clean_lines: List[Tuple[str, str]],
        source_ref: str
    ) -> LogIntelligenceReport:
        miner = self._build_drain3_miner()
        cluster_metadata: Dict[int, Dict[str, Any]] = {}

        for line, ts in clean_lines:
            result = miner.add_log_message(line)
            cid = result.get("cluster_id")
            if cid not in cluster_metadata:
                cluster_metadata[cid] = {
                    "first_seen": ts,
                    "last_seen": ts,
                    "samples": [line],
                    "count": 1
                }
            else:
                cluster_metadata[cid]["last_seen"] = ts
                cluster_metadata[cid]["count"] += 1
                if len(cluster_metadata[cid]["samples"]) < 5:
                    cluster_metadata[cid]["samples"].append(line)

        templates: List[LogTemplateRecord] = []
        for cluster in miner.drain.clusters:
            cid = cluster.cluster_id
            template_text = cluster.get_template()
            meta = cluster_metadata.get(cid, {
                "first_seen": clean_lines[0][1],
                "last_seen": clean_lines[-1][1],
                "samples": [],
                "count": cluster.size
            })

            templates.append(LogTemplateRecord(
                template_id=f"tmpl_{cid}",
                template_text=template_text,
                occurrence_count=cluster.size,
                first_seen=meta["first_seen"],
                last_seen=meta["last_seen"],
                sample_messages=meta["samples"],
                source_refs=[source_ref]
            ))

        # Sort templates by frequency (highest occurrence first)
        templates.sort(key=lambda t: t.occurrence_count, reverse=True)

        return LogIntelligenceReport(
            implementation_used="drain3",
            templates=templates,
            total_messages_processed=len(clean_lines),
            unique_templates_count=len(templates),
            degraded_mode=False,
            status_message=f"Successfully extracted {len(templates)} templates using Drain3"
        )

    def _mine_with_fallback(
        self,
        clean_lines: List[Tuple[str, str]],
        source_ref: str
    ) -> LogIntelligenceReport:
        """
        Deterministic regex-based log normalizer that replaces variable tokens
        (numbers, UUIDs, IPs, hex) with standard tags (<NUM>, <UUID>, <IP>, <HEX>).
        """
        cluster_map: Dict[str, Dict[str, Any]] = {}

        for line, ts in clean_lines:
            # Mask UUIDs
            tmpl = re.sub(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                "<UUID>",
                line
            )
            # Mask IP addresses
            tmpl = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP>", tmpl)
            # Mask Hex
            tmpl = re.sub(r"\b0x[0-9a-fA-F]+\b", "<HEX>", tmpl)
            # Mask Numbers
            tmpl = re.sub(r"((?<=[^A-Za-z0-9])|^)[\-\+]?\d+((?=[^A-Za-z0-9])|$)", "<NUM>", tmpl)

            if tmpl not in cluster_map:
                cluster_map[tmpl] = {
                    "first_seen": ts,
                    "last_seen": ts,
                    "samples": [line],
                    "count": 1
                }
            else:
                cluster_map[tmpl]["last_seen"] = ts
                cluster_map[tmpl]["count"] += 1
                if len(cluster_map[tmpl]["samples"]) < 5:
                    cluster_map[tmpl]["samples"].append(line)

        templates: List[LogTemplateRecord] = []
        for idx, (tmpl_text, meta) in enumerate(cluster_map.items(), start=1):
            templates.append(LogTemplateRecord(
                template_id=f"tmpl_{idx}",
                template_text=tmpl_text,
                occurrence_count=meta["count"],
                first_seen=meta["first_seen"],
                last_seen=meta["last_seen"],
                sample_messages=meta["samples"],
                source_refs=[source_ref]
            ))

        templates.sort(key=lambda t: t.occurrence_count, reverse=True)

        return LogIntelligenceReport(
            implementation_used="deterministic_fallback",
            templates=templates,
            total_messages_processed=len(clean_lines),
            unique_templates_count=len(templates),
            degraded_mode=False if not self.force_fallback else False,
            status_message=f"Extracted {len(templates)} templates using deterministic fallback normalizer"
        )
