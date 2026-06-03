from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session
from .entities import Finding, InvestigationContext
from .models import Investigation, Finding as FindingModel
from .utils import now_iso, generate_investigation_id


class InvestigationEngine:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, entity_type: str, target: str, investigator: str | None = None) -> InvestigationContext:
        investigation_id = generate_investigation_id(self.session)
        investigation = Investigation(
            investigation_id=investigation_id,
            entity_type=entity_type,
            target=target,
            status="running",
            timeline="[]",
            investigator=investigator,
        )
        self.session.add(investigation)
        self.session.commit()
        context = InvestigationContext(investigation_id=investigation_id, entity_type=entity_type, target=target)
        context.add_event("Investigation Started")
        if investigator:
            context.metadata["investigator"] = investigator
        return context

    def record(self, context: InvestigationContext) -> str:
        investigation = self.session.query(Investigation).filter_by(investigation_id=context.investigation_id).one()
        investigation.status = "complete"
        investigation.timeline = "\n".join(context.timeline)
        for finding in context.findings:
            timestamp_str = finding.timestamp
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str.replace("Z", "+00:00")
            model = FindingModel(
                investigation_id=investigation.id,
                category=finding.category,
                title=finding.title,
                details=finding.details,
                source=finding.source,
                timestamp=datetime.fromisoformat(timestamp_str),
                confidence=finding.confidence,
            )
            self.session.add(model)
        # persist case-level metadata if present
        case_risk = context.metadata.get("case_risk")
        if case_risk:
            try:
                investigation.risk_score = float(case_risk.get("risk_score", 0.0))
            except Exception:
                investigation.risk_score = 0.0
            try:
                investigation.confidence_score = float(case_risk.get("entity_confidence", 0.0))
            except Exception:
                investigation.confidence_score = 0.0

        if context.metadata.get("investigator"):
            investigation.investigator = context.metadata.get("investigator")

        # store structured evidence summary for quick access
        try:
            import json

            evidence = {
                "findings_count": len(context.findings),
                "top_sources": sorted({f.source for f in context.findings if f.source})[:10],
            }
            investigation.evidence_json = json.dumps(evidence)
        except Exception:
            pass

        self.session.commit()
        return investigation.investigation_id

    def add_finding(self, context: InvestigationContext, finding: Finding) -> None:
        context.findings.append(finding)
        context.add_event(f"Finding collected: {finding.title}")

    def add_event(self, context: InvestigationContext, event: str) -> None:
        context.add_event(event)
