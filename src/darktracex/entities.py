from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SourceReference:
    source: str
    timestamp: str
    confidence: float
    details: str


@dataclass
class Finding:
    category: str
    title: str
    details: str
    source: str
    timestamp: str
    confidence: float


@dataclass
class ModuleResult:
    findings: list[Finding] = field(default_factory=list)
    timeline: list[str] = field(default_factory=list)


@dataclass
class InvestigationContext:
    investigation_id: str
    entity_type: str
    target: str
    findings: list[Finding] = field(default_factory=list)
    timeline: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def add_event(self, event: str) -> None:
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        self.timeline.append(f"[{timestamp}] {event}")
