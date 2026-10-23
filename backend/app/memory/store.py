"""
Incident Memory Store for RootTrace.
Lightweight persistent storage (JSON / in-memory file backed) for resolved incidents,
postmortems, and searchable knowledge items.
"""
from typing import Dict, Any, List, Optional
import os
import json
import datetime
from ..models.domain import IncidentReport, Incident


class IncidentMemoryStore:
    def __init__(self, storage_path: str = "incident_memory.json"):
        self.storage_path = storage_path
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self._memory = json.load(f)
            except Exception:
                self._memory = {}

    def _save(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._memory, f, indent=2)
        except Exception:
            pass

    def store_postmortem(self, report: IncidentReport):
        self._memory[report.incident_id] = report.model_dump()
        self._save()

    def get_postmortem(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return self._memory.get(incident_id)

    def list_all(self) -> List[Dict[str, Any]]:
        return list(self._memory.values())

    def search(self, query: str) -> List[Dict[str, Any]]:
        q = query.lower()
        results = []
        for item in self._memory.values():
            text = f"{item.get('title', '')} {item.get('root_cause', '')} {item.get('remediation_summary', '')}".lower()
            if q in text:
                results.append(item)
        return results
