from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session
from .entities import Finding, InvestigationContext
from .models import Investigation, Finding as FindingModel
from .utils import now_iso, generate_investigation_id


class InvestigationEngine:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, entity_type: str, target: str) -> InvestigationContext:
        investigation_id = generate_investigation_id(self.session)
        investigation = Investigation(
            investigation_id=investigation_id,
            entity_type=entity_type,
            target=target,
            status="running",
            timeline="[]"
        )
        self.session.add(investigation)
        self.session.commit()
        context = InvestigationContext(investigation_id=investigation_id, entity_type=entity_type, target=target)
        context.add_event("Investigation Started")
        return context

    def record(self, context: InvestigationContext) -> str:
        investigation = self.session.query(Investigation).filter_by(investigation_id=context.investigation_id).one()
        investigation.status = "complete"
        investigation.timeline = "\n".join(context.timeline)
        for finding in context.findings:
            model = FindingModel(
                investigation_id=investigation.id,
                category=finding.category,
                title=finding.title,
                details=finding.details,
                source=finding.source,
                timestamp=datetime.fromisoformat(finding.timestamp),
                confidence=finding.confidence,
            )
            self.session.add(model)
        self.session.commit()
        return investigation.investigation_id

    def add_finding(self, context: InvestigationContext, finding: Finding) -> None:
        context.findings.append(finding)
        context.add_event(f"Finding collected: {finding.title}")

    def add_event(self, context: InvestigationContext, event: str) -> None:
        context.add_event(event)
