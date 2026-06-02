from __future__ import annotations

import csv
from pathlib import Path
from datetime import datetime
from typing import Any
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from .entities import Finding


class ReportEngine:
    def __init__(self, workspace_dir: Path) -> None:
        self.workspace_dir = workspace_dir
        self.reports_dir = workspace_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _render_header(self, title: str) -> list:
        header_style = ParagraphStyle("Header", fontSize=18, leading=22, spaceAfter=12)
        return [Paragraph(title, header_style), Spacer(1, 0.2 * inch)]

    def generate_json(
        self,
        investigation_id: str,
        summary: str,
        findings: list[Finding],
        timeline: list[str],
        sources: list[str],
        metadata: dict[str, Any] | None = None,
        correlation: dict[str, Any] | None = None,
        leads: list[Any] | None = None,
    ) -> Path:
        path = self.reports_dir / f"{investigation_id}.json"
        content = {
            "investigation_id": investigation_id,
            "summary": summary,
            "findings": [finding.__dict__ for finding in findings],
            "timeline": timeline,
            "sources": sources,
            "metadata": metadata or {},
            "correlation": correlation or {},
            "leads": [lead.__dict__ if hasattr(lead, "__dict__") else lead for lead in (leads or [])],
            "generated_at": datetime.utcnow().isoformat(),
        }
        path.write_text(__import__("json").dumps(content, indent=2), encoding="utf-8")
        return path

    def generate_csv(self, investigation_id: str, findings: list[Finding]) -> Path:
        path = self.reports_dir / f"{investigation_id}.csv"
        with path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["category", "title", "details", "source", "timestamp", "confidence"])
            for finding in findings:
                writer.writerow([finding.category, finding.title, finding.details, finding.source, finding.timestamp, finding.confidence])
        return path

    def generate_html(
        self,
        investigation_id: str,
        summary: str,
        findings: list[Finding],
        timeline: list[str],
        sources: list[str],
        metadata: dict[str, Any] | None = None,
        correlation: dict[str, Any] | None = None,
        leads: list[Any] | None = None,
    ) -> Path:
        path = self.reports_dir / f"{investigation_id}.html"
        items = "".join(
            f"<li><strong>{finding.category}</strong>: {finding.title} (<em>{finding.source}</em>)</li>"
            for finding in findings
        )
        timeline_html = "".join(f"<li>{event}</li>" for event in timeline)
        sources_html = "".join(f"<li>{source}</li>" for source in sources)
        metadata_html = "".join(
            f"<li>{key}: {value}</li>" for key, value in (metadata or {}).items()
        )
        correlation_html = "".join(
            f"<li>{item['source']} → {item['target']} ({item['type']}, confidence {item['confidence']:.2f})</li>"
            for item in (correlation or {}).get("top_correlations", [])
        )
        leads_html = "".join(
            f"<li>{lead_data.get('category', '')}: <strong>{lead_data.get('title', '')}</strong> - {lead_data.get('description', '')} (Confidence: {lead_data.get('confidence', 0.0):.2f})</li>"
            for lead in (leads or [])
            for lead_data in [lead.__dict__ if hasattr(lead, "__dict__") else lead]
        )
        html = f"""
        <html>
        <head><title>{investigation_id} Report</title></head>
        <body>
        <h1>DarkTrace X Investigation {investigation_id}</h1>
        <h2>Executive Summary</h2>
        <p>{summary}</p>
        <h2>Metadata</h2>
        <ul>{metadata_html}</ul>
        <h2>Top Correlations</h2>
        <ul>{correlation_html}</ul>
        <h2>Recommended Leads</h2>
        <ul>{leads_html}</ul>
        <h2>Findings</h2>
        <ul>{items}</ul>
        <h2>Timeline</h2>
        <ul>{timeline_html}</ul>
        <h2>Sources</h2>
        <ul>{sources_html}</ul>
        </body>
        </html>
        """
        path.write_text(html, encoding="utf-8")
        return path

    def generate_pdf(
        self,
        investigation_id: str,
        summary: str,
        findings: list[Finding],
        timeline: list[str],
        sources: list[str],
        metadata: dict[str, Any] | None = None,
        correlation: dict[str, Any] | None = None,
        leads: list[Any] | None = None,
    ) -> Path:
        path = self.reports_dir / f"{investigation_id}.pdf"
        doc = SimpleDocTemplate(str(path), pagesize=letter)
        story = self._render_header(f"DarkTrace X Investigation {investigation_id}")
        story.append(Paragraph("Executive Summary", ParagraphStyle("Section", fontSize=14, leading=18, spaceAfter=8)))
        story.append(Paragraph(summary, ParagraphStyle("Body", fontSize=11, leading=14)))
        story.append(Spacer(1, 0.2 * inch))

        if metadata:
            story.append(Paragraph("Metadata", ParagraphStyle("Section", fontSize=14, leading=18, spaceAfter=8)))
            for key, value in metadata.items():
                story.append(Paragraph(f"{key}: {value}", ParagraphStyle("Body", fontSize=10, leading=13)))
            story.append(Spacer(1, 0.1 * inch))

        if correlation and correlation.get("top_correlations"):
            story.append(Paragraph("Top Correlations", ParagraphStyle("Section", fontSize=14, leading=18, spaceAfter=8)))
            for item in correlation.get("top_correlations", []):
                story.append(Paragraph(
                    f"{item['source']} → {item['target']} ({item['type']}; confidence {item['confidence']:.2f})",
                    ParagraphStyle("Body", fontSize=10, leading=13)
                ))
            story.append(Spacer(1, 0.1 * inch))

        if leads:
            story.append(Paragraph("Recommended Leads", ParagraphStyle("Section", fontSize=14, leading=18, spaceAfter=8)))
            for lead in leads:
                lead_data = lead.__dict__ if hasattr(lead, "__dict__") else lead
                story.append(Paragraph(
                    f"{lead_data.get('category', '')}: {lead_data.get('title', '')} ({lead_data.get('confidence', 0.0):.2f})",
                    ParagraphStyle("ItemHeading", fontSize=12, leading=14, textColor=colors.darkblue)
                ))
                story.append(Paragraph(
                    f"{lead_data.get('description', '')}",
                    ParagraphStyle("Body", fontSize=10, leading=13)
                ))
                story.append(Spacer(1, 0.05 * inch))
            story.append(Spacer(1, 0.1 * inch))

        story.append(Paragraph("Findings", ParagraphStyle("Section", fontSize=14, leading=18, spaceAfter=8)))
        for finding in findings:
            story.append(Paragraph(f"<strong>{finding.category}</strong>: {finding.title}", ParagraphStyle("ItemHeading", fontSize=12, leading=14, textColor=colors.darkblue)))
            story.append(Paragraph(finding.details, ParagraphStyle("Body", fontSize=10, leading=13)))
            story.append(Spacer(1, 0.05 * inch))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Timeline", ParagraphStyle("Section", fontSize=14, leading=18, spaceAfter=8)))
        for event in timeline:
            story.append(Paragraph(event, ParagraphStyle("Body", fontSize=10, leading=13)))
        story.append(Spacer(1, 0.2 * inch))
        story.append(Paragraph("Sources", ParagraphStyle("Section", fontSize=14, leading=18, spaceAfter=8)))
        for source in sources:
            story.append(Paragraph(source, ParagraphStyle("Body", fontSize=10, leading=13)))
        doc.build(story)
        return path
