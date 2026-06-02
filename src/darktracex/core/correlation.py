"""Cross-Entity Correlation Engine for DarkTrace X.

Builds relationship graphs between entities and detects overlaps across all investigation modules.
Implements Maltego-style correlation with confidence scoring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from ..entities import Finding, Lead, ModuleResult
from ..utils import now_iso, round_confidence


@dataclass
class Entity:
    """Represents a correlated entity in the investigation graph."""

    eid: str
    entity_type: str  # phone, email, username, domain, ip, organization
    value: str
    confidence: float = 0.5
    findings: List[Finding] = field(default_factory=list)
    timeline: List[str] = field(default_factory=list)

    def __hash__(self):
        return hash((self.entity_type, self.value.lower()))

    def __eq__(self, other):
        if not isinstance(other, Entity):
            return False
        return self.entity_type == other.entity_type and self.value.lower() == other.value.lower()


@dataclass
class Relationship:
    """Represents a correlation link between two entities."""

    entity1: Entity
    entity2: Entity
    relationship_type: str  # overlap, reference, shared_infrastructure, etc.
    confidence: float
    evidence: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=now_iso)


class CorrelationEngine:
    """Maltego-style entity correlation engine for cyber investigations."""

    def __init__(self):
        self.graph: nx.DiGraph = nx.DiGraph()
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []
        self.leads: List[Lead] = []
        self.timeline: List[str] = []

    def reset(self) -> None:
        """Reset the correlation engine for a new investigation."""
        self.graph.clear()
        self.entities.clear()
        self.relationships.clear()
        self.leads.clear()
        self.timeline.clear()

    def add_module_result(
        self, module_name: str, target: str, result: ModuleResult
    ) -> Entity:
        """Ingest module result and extract correlated entities."""

        base_entity = Entity(
            eid=f"{module_name}_{target}",
            entity_type=module_name.lower().replace(" ", "_"),
            value=target,
            findings=result.findings,
            timeline=result.timeline,
        )
        if result.findings:
            confidence_avg = sum(f.confidence for f in result.findings) / len(result.findings)
            base_entity.confidence = round_confidence(confidence_avg)

        self.entities[base_entity.eid] = base_entity
        self.graph.add_node(base_entity.eid, entity=base_entity)

        # Extract secondary entities from findings
        extracted = self._extract_entities_from_findings(result.findings, module_name)
        for entity in extracted:
            if entity.eid not in self.entities:
                self.entities[entity.eid] = entity
                self.graph.add_node(entity.eid, entity=entity)
            self._correlate_entities(base_entity, entity, result.findings)

        self.timeline.append(
            f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
            f"Ingested {module_name} module: {target} "
            f"({len(extracted)} secondary entities extracted)"
        )

        return base_entity

    def _extract_entities_from_findings(
        self, findings: List[Finding], source_module: str
    ) -> List[Entity]:
        """Extract potential entities from finding details."""

        extracted = []
        seen_ids: Set[str] = set()
        email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        domain_regex = r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}"
        ip_regex = r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"

        for finding in findings:
            text = f"{finding.title} {finding.details}".lower()

            # Extract emails
            for match in re.finditer(email_regex, text):
                email = match.group()
                entity_id = f"email_{email}"
                if entity_id not in self.entities and entity_id not in seen_ids:
                    extracted.append(
                        Entity(
                            eid=entity_id,
                            entity_type="email",
                            value=email,
                            confidence=round_confidence(0.75),
                        )
                    )
                    seen_ids.add(entity_id)

            # Extract domains
            for match in re.finditer(domain_regex, text):
                domain = match.group()
                if (
                    "." in domain
                    and len(domain) > 5
                    and not domain.startswith(".")
                ):
                    entity_id = f"domain_{domain}"
                    if entity_id not in self.entities and entity_id not in seen_ids:
                        extracted.append(
                            Entity(
                                eid=entity_id,
                                entity_type="domain",
                                value=domain,
                                confidence=round_confidence(0.70),
                            )
                        )
                        seen_ids.add(entity_id)

            # Extract IPs
            for match in re.finditer(ip_regex, text):
                ip = match.group()
                if not (
                    ip.startswith("192.168.")
                    or ip.startswith("10.")
                    or ip.startswith("172.")
                    or ip == "0.0.0.0"
                ):
                    entity_id = f"ip_{ip}"
                    if entity_id not in self.entities and entity_id not in seen_ids:
                        extracted.append(
                            Entity(
                                eid=entity_id,
                                entity_type="ip",
                                value=ip,
                                confidence=round_confidence(0.80),
                            )
                        )
                        seen_ids.add(entity_id)

        return extracted

    def _correlate_entities(
        self, entity1: Entity, entity2: Entity, findings: List[Finding]
    ) -> None:
        """Create relationship between entities based on overlap."""

        rel_type = self._determine_relationship_type(entity1, entity2)
        if not rel_type:
            return

        confidence = self._calculate_correlation_confidence(
            entity1, entity2, findings
        )

        rel = Relationship(
            entity1=entity1,
            entity2=entity2,
            relationship_type=rel_type,
            confidence=confidence,
            evidence=[f.title for f in findings[:3]],
        )

        self.relationships.append(rel)
        self.graph.add_edge(
            entity1.eid,
            entity2.eid,
            relationship=rel_type,
            confidence=confidence,
        )

        self.timeline.append(
            f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
            f"Correlated {entity1.entity_type}:{entity1.value} -> "
            f"{entity2.entity_type}:{entity2.value} ({rel_type}, conf: {confidence})"
        )

    def _determine_relationship_type(
        self, entity1: Entity, entity2: Entity
    ) -> Optional[str]:
        """Determine correlation type based on entity types."""

        type_pair = (entity1.entity_type, entity2.entity_type)

        # Email domain from email address
        if type_pair == ("email", "domain") and "@" in entity1.value:
            if entity1.value.split("@")[1].lower() == entity2.value.lower():
                return "email_domain"

        # IP from hostname/domain (reverse DNS or A record)
        if type_pair == ("ip", "domain") or type_pair == ("domain", "ip"):
            return "shared_infrastructure"

        # Shared domain in organization context
        if (
            entity1.entity_type == "organization"
            and entity2.entity_type == "domain"
        ):
            return "organization_domain"

        # Username across platforms
        if entity1.entity_type == "username" and entity2.entity_type == "username":
            if entity1.value.lower() == entity2.value.lower():
                return "cross_platform"

        # Generic reference
        if entity1.entity_type != entity2.entity_type:
            return "reference"

        return None

    def _calculate_correlation_confidence(
        self, entity1: Entity, entity2: Entity, findings: List[Finding]
    ) -> float:
        """Calculate confidence score for correlation."""

        confidence = 0.5

        # Perfect match gets high confidence
        if entity1.value.lower() == entity2.value.lower():
            confidence = 0.95
        # Substring match or partial match
        elif (
            entity1.value.lower() in entity2.value.lower()
            or entity2.value.lower() in entity1.value.lower()
        ):
            confidence = 0.75
        # Reference in findings
        elif any(
            entity2.value.lower() in f.details.lower() for f in findings
        ):
            confidence = 0.70

        # Adjust based on entity types
        rel_type = self._determine_relationship_type(entity1, entity2)
        if rel_type == "email_domain":
            confidence = 0.98
        elif rel_type == "shared_infrastructure":
            confidence = 0.85
        elif rel_type == "cross_platform":
            confidence = 0.90

        return round_confidence(confidence)

    def get_entity(self, eid: str) -> Optional[Entity]:
        """Retrieve entity by ID."""
        return self.entities.get(eid)

    def get_case_risk(self) -> Dict[str, float | str]:
        """Estimate overall case risk and correlation intensity."""
        total_entities = max(1, len(self.entities))
        total_relationships = max(1, len(self.relationships))
        entity_confidence = sum(e.confidence for e in self.entities.values()) / total_entities
        relationship_confidence = sum(r.confidence for r in self.relationships) / total_relationships
        relationship_density = min(1.0, len(self.relationships) / total_entities)
        score = round_confidence(
            (entity_confidence * 0.35)
            + (relationship_confidence * 0.45)
            + (relationship_density * 0.20)
        )
        if score >= 0.80:
            level = "HIGH"
        elif score >= 0.60:
            level = "MEDIUM"
        elif score >= 0.40:
            level = "LOW"
        else:
            level = "VERY LOW"

        return {
            "risk_score": score,
            "risk_level": level,
            "relationship_density": round_confidence(relationship_density),
            "entity_confidence": round_confidence(entity_confidence),
            "relationship_confidence": round_confidence(relationship_confidence),
        }

    def get_recommended_leads(self) -> List[Lead]:
        """Generate investigation leads based on correlation signals."""
        if self.leads:
            return self.leads

        leads: list[Lead] = []
        strong_relationships = sorted(
            self.relationships, key=lambda r: r.confidence, reverse=True
        )[:5]
        for rel in strong_relationships:
            leads.append(
                Lead(
                    category="Correlation Lead",
                    title=f"Investigate relationship between {rel.entity1.value} and {rel.entity2.value}",
                    description=(
                        f"Detected a {rel.relationship_type} connection with confidence {rel.confidence}. "
                        f"Evidence: {', '.join(rel.evidence[:2])}."
                    ),
                    target=f"{rel.entity1.value} -> {rel.entity2.value}",
                    confidence=rel.confidence,
                )
            )

        if not leads and self.entities:
            for entity in self.entities.values():
                if self.graph.degree(entity.eid) == 0 and len(leads) < 3:
                    leads.append(
                        Lead(
                            category="Entity Lead",
                            title=f"Investigate isolated entity {entity.value}",
                            description=(
                                "Entity was detected but has no strong relationship links. "
                                "Validate its origin and whether it belongs to the target threat cluster."
                            ),
                            target=entity.value,
                            confidence=entity.confidence,
                        )
                    )

        self.leads = leads
        return leads

    def get_related_entities(
        self, eid: str, relationship_type: Optional[str] = None
    ) -> List[Tuple[Entity, Relationship]]:
        """Get all entities related to a target entity."""

        if eid not in self.graph:
            return []

        related = []
        for neighbor_id in list(self.graph.successors(eid)) + list(
            self.graph.predecessors(eid)
        ):
            neighbor = self.entities.get(neighbor_id)
            if neighbor:
                rel = next(
                    (
                        r
                        for r in self.relationships
                        if (
                            (r.entity1.eid == eid and r.entity2.eid == neighbor_id)
                            or (
                                r.entity1.eid == neighbor_id
                                and r.entity2.eid == eid
                            )
                        )
                        and (
                            relationship_type is None
                            or r.relationship_type == relationship_type
                        )
                    ),
                    None,
                )
                if rel:
                    related.append((neighbor, rel))

        return related

    def get_investigation_graph(self) -> nx.DiGraph:
        """Return the underlying NetworkX graph."""
        return self.graph

    def get_correlation_summary(self) -> Dict:
        """Generate summary of all correlations."""

        summary = {
            "timestamp": now_iso(),
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
            "entity_breakdown": {},
            "top_correlations": [],
            "recommended_leads": [lead.__dict__ for lead in self.get_recommended_leads()],
            "timeline": self.timeline[-20:],  # Last 20 events
        }

        # Entity breakdown
        for entity_type in set(e.entity_type for e in self.entities.values()):
            count = sum(
                1 for e in self.entities.values() if e.entity_type == entity_type
            )
            summary["entity_breakdown"][entity_type] = count

        # Top correlations by confidence
        sorted_rels = sorted(
            self.relationships, key=lambda r: r.confidence, reverse=True
        )
        summary["top_correlations"] = [
            {
                "source": f"{r.entity1.entity_type}:{r.entity1.value}",
                "target": f"{r.entity2.entity_type}:{r.entity2.value}",
                "type": r.relationship_type,
                "confidence": r.confidence,
                "evidence": r.evidence,
            }
            for r in sorted_rels[:10]
        ]

        return summary

    def export_to_dict(self) -> Dict:
        """Export correlation engine state to dictionary (for JSON export)."""

        return {
            "timestamp": now_iso(),
            "entities": [
                {
                    "id": e.eid,
                    "type": e.entity_type,
                    "value": e.value,
                    "confidence": e.confidence,
                    "findings_count": len(e.findings),
                    "timeline_events": len(e.timeline),
                }
                for e in self.entities.values()
            ],
            "relationships": [
                {
                    "source_id": r.entity1.eid,
                    "target_id": r.entity2.eid,
                    "type": r.relationship_type,
                    "confidence": r.confidence,
                    "evidence": r.evidence,
                    "timestamp": r.timestamp,
                }
                for r in self.relationships
            ],
            "summary": self.get_correlation_summary(),
        }
