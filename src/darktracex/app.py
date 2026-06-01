from __future__ import annotations

import asyncio
import logging
import textwrap
from typing import Any

import textual
from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from .config import AppConfig
from .core.correlation import CorrelationEngine
from .db import init_db, SessionLocal
from .entities import Finding, InvestigationContext
from .investigation import InvestigationEngine
from .modules import phone, email, domain, ip, organization, username
from .plugin_manager import PluginRegistry
from .reports import ReportEngine

MENU_ITEMS = [
    "Phone Number",
    "Email Address",
    "Domain",
    "IP Address",
    "Organization",
    "Website",
    "Social Profile",
    "Investigations",
    "Reports",
    "Settings",
    "Exit",
]

MODULE_MAP = {
    "Phone Number": phone.run_phone_intel,
    "Email Address": email.run_email_intel,
    "Domain": domain.run_domain_intel,
    "IP Address": ip.run_ip_intel,
    "Organization": organization.run_org_intel,
    "Website": domain.run_domain_intel,
    "Social Profile": username.run_username_intel,
}


class Banner(Static):
    def render(self) -> Panel:
        width = max(self.size.width or 80, 80)
        if width >= 90:
            ascii_art = """
██████╗  █████╗ ██████╗ ██╗  ██╗████████╗██████╗  █████╗  ██████╗███████╗
██╔══██╗██╔══██╗██╔══██╗██║ ██╔╝╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██╔════╝
██║  ██║███████║██████╔╝█████╔╝    ██║   ██████╔╝███████║██║     █████╗
██║  ██║██╔══██║██╔══██╗██╔═██╗    ██║   ██╔══██╗██╔══██║██║     ██╔══╝
██████╔╝██║  ██║██║  ██║██║  ██╗   ██║   ██║  ██║██║  ██║╚██████╗███████╗
╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝

                       X

Cyber Intelligence Investigation Engine

MADE IN INDIA 🇮🇳

Author: Darkscripters
"""
        else:
            ascii_art = """
 ██████╗  █████╗ ██████╗ ██╗  ██╗████████╗██████╗  █████╗
██╔══██╗██╔══██╗██╔══██╗██║ ██╔╝╚══██╔══╝██╔══██╗██╔══██╗
██║  ██║███████║██████╔╝█████╔╝    ██║   ██████╔╝███████║
██║  ██║██╔══██║██╔══██╗██╔═██╗    ██║   ██╔══██╗██╔══██║
██████╔╝██║  ██║██║  ██║██║  ██╗   ██║   ██║  ██║██║  ██║
╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝

                     DARKTRACE X

        Cyber Intelligence Investigation Engine
        MADE IN INDIA 🇮🇳
        Author: Darkscripters
"""
        banner_text = Text(ascii_art, style="bold red on black", justify="center")
        return Panel(
            banner_text,
            border_style="bright_cyan",
            style="on black",
            padding=(1, 2),
        )


class StatusPanel(Static):
    status_text = reactive("Initializing...")

    def update_status(self, content: str) -> None:
        self.status_text = content
        self.refresh()

    def render(self) -> Panel:
        return Panel(self.status_text, title="Status", border_style="green")


class OutputPanel(Static):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._entries: list[RenderableType] = []

    def write(self, data: str | RenderableType, scroll_end: bool | None = None) -> "OutputPanel":
        if isinstance(data, str):
            try:
                entry = Text.from_markup(data, style="white")
            except Exception:
                entry = Text(data, style="white")
            self._entries.append(entry)
        else:
            self._entries.append(data)
        self.refresh()
        return self

    def clear(self) -> None:
        self._entries.clear()
        self.refresh()

    def render(self) -> RenderableType:
        if self._entries:
            body = Group(*self._entries)
        else:
            body = Text("Ready. Select a module to investigate.", style="green")
        return Panel(
            body,
            title="Investigation Output",
            border_style="bright_magenta",
            padding=(1, 1),
            expand=True,
        )


class DarkTraceXApp(App):
    CSS_PATH = "darktracex.tcss"
    BINDINGS = [("q", "quit","Quit")]

    selected_module = reactive("Phone Number")
    current_workspace = reactive("")
    active_investigations = reactive(0)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.plugin_registry = PluginRegistry(config)
        self.current_workspace = str(config.workspace_dir)
        self.report_engine = ReportEngine(config.workspace_dir)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[logging.StreamHandler()],
        )
        self.logger = logging.getLogger("darktracex")
        self._check_textual_version()

        try:
            init_db()
            self.logger.info("Database initialized successfully")
        except Exception:
            self.logger.exception("Database initialization failed")

        self.session = SessionLocal()
        self.investigation_engine = InvestigationEngine(self.session)
        self.correlation_engine = CorrelationEngine()
        self.logger.info("DarkTrace X initialized. Workspace: %s", self.current_workspace)

    def _check_textual_version(self) -> None:
        version = getattr(textual, "__version__", "0.0.0")
        try:
            major, minor, *_ = [int(part) for part in version.split(".") if part.isdigit()]
        except Exception:
            major, minor = 0, 0
        if major == 0 and minor < 27:
            self.logger.warning(
                "Installed Textual version %s may not be compatible with DarkTrace X. Please upgrade to textual >= 0.27.0.",
                version,
            )
        else:
            self.logger.info("Detected Textual version %s", version)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Banner()
        with Horizontal():
            with Vertical(id="left-pane"):
                yield Static("Main Menu", id="menu-title")
                menu_items = []
                for item in MENU_ITEMS:
                    row = ListItem(Label(item))
                    row.module_name = item
                    menu_items.append(row)
                list_view = ListView(*menu_items, id="menu-list")
                yield list_view
                yield Input(placeholder="Enter target and press Enter", id="target-input")
                yield Button("Run Investigation", id="run-button", variant="primary")
            with Vertical(id="right-pane"):
                yield StatusPanel(id="status-panel")
                yield OutputPanel(id="output-panel")
        yield Footer()

    async def on_mount(self) -> None:
        self.status = self.query_one(StatusPanel)
        self.output = self.query_one(OutputPanel)
        self.update_header()
        try:
            loaded_plugins = self.plugin_registry.load()
            self.logger.info("Loaded %d plugins", len(loaded_plugins))
        except Exception as exc:
            self.logger.exception("Plugin loading failed")
            self.output.write(f"Plugin loading failed: {exc}")
        self.update_status()

    def update_header(self) -> None:
        self.query_one(Header).sub_title = f"Workspace: {self.current_workspace} | Plugins: {len(self.plugin_registry.active)}"

    def update_status(self) -> None:
        self.status.update_status(
            f"Module: {self.selected_module}\nActive Investigations: {self.active_investigations}\nLoaded Plugins: {len(self.plugin_registry.active)}"
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.selected_module = getattr(event.item, "module_name", "")
        self.output.write(f"Selected module: {self.selected_module}. Enter a target and run investigation.")
        self.update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-button":
            target_input = self.query_one(Input)
            target = target_input.value.strip()
            if not target:
                self.output.write("Please enter a valid target before running an investigation.")
                return
            if self.selected_module == "Exit":
                self.exit()
                return
            asyncio.create_task(self.start_investigation(self.selected_module, target))

    async def start_investigation(self, module_name: str, target: str) -> None:
        self.active_investigations += 1
        self.update_status()
        self.output.clear()
        self.output.write(f"Starting {module_name} investigation for {target}...")
        self.status.update_status("Collecting intelligence...")
        self.logger.info("Running module: %s", module_name)
        self.logger.info("Target: %s", target)
        await asyncio.sleep(0.1)

        handler = MODULE_MAP.get(module_name)
        if handler is None:
            self.output.write(f"The module '{module_name}' is currently unavailable.")
            self.active_investigations -= 1
            self.update_status()
            return

        try:
            results = await asyncio.to_thread(handler, target)
            context = self.investigation_engine.create(module_name, target)
            for finding in results.findings:
                self.investigation_engine.add_finding(context, finding)
            for event in results.timeline:
                self.investigation_engine.add_event(context, event)
            self.investigation_engine.record(context)
            self.correlation_engine.add_module_result(module_name, target, results)

            self.logger.info("Findings: %d", len(results.findings))
            self.logger.info("Timeline: %d", len(results.timeline))

            for section in self.format_results(context):
                self.output.write(section)
            self.output.write(self._build_correlation_summary_panel())

            self.status.update_status("Investigation complete. Generate a report from the reports menu.")
        except Exception as exc:
            self.logger.exception("Investigation error")
            self.output.write(f"Investigation error: {exc}")
        finally:
            self.active_investigations -= 1
            self.update_status()

    def format_results(self, context: InvestigationContext) -> list[RenderableType]:
        sections: list[RenderableType] = []
        sections.append(self._build_executive_summary_panel(context))
        sections.append(self._build_metadata_panel(context))
        sections.append(self._build_timeline_panel(context))
        sections.extend(self._build_findings_sections(context))
        sections.append(self._build_risk_panel(context))
        sections.append(self._build_correlation_panel(context))
        sections.append(self._build_evidence_panel(context))
        sections.append(self._build_analyst_notes_panel(context))
        return sections

    def _build_executive_summary_panel(self, context: InvestigationContext) -> RenderableType:
        summary = Text()
        summary.append("Executive Summary\n", style="cyan bold underline")
        summary.append("----------------------------------------\n", style="cyan")
        summary.append(f"Target: {context.target}\n", style="white bold")
        summary.append(f"Module: {context.entity_type}\n", style="white")
        summary.append(f"Findings: {len(context.findings)}\n", style="white")
        summary.append(f"Timeline events: {len(context.timeline)}\n", style="white")
        if context.findings:
            highest = max(context.findings, key=lambda f: f.confidence)
            summary.append(f"Highest confidence finding: {highest.title} ({highest.confidence:.2f})\n", style="green")
        else:
            summary.append("No verifiable public evidence discovered.\n", style="yellow")

        return Panel(
            summary,
            title="Executive Summary",
            border_style="cyan",
            padding=(1, 1),
        )

    def _build_metadata_panel(self, context: InvestigationContext) -> RenderableType:
        metadata = []
        metadata.append(("Investigation ID", context.investigation_id or "N/A"))
        metadata.append(("Target", context.target))
        metadata.append(("Module", context.entity_type))
        if context.metadata:
            for key, value in context.metadata.items():
                metadata.append((str(key), str(value)))

        lines = Text()
        for name, value in metadata:
            lines.append(f"{name}: ", style="cyan bold")
            lines.append(f"{value}\n", style="white")

        return Panel(
            lines,
            title="Investigation Metadata",
            border_style="cyan",
            padding=(1, 1),
        )

    def _build_timeline_panel(self, context: InvestigationContext) -> RenderableType:
        timeline_text = Text()
        if context.timeline:
            for event in context.timeline:
                timeline_text.append("[✓] ", style="green")
                timeline_text.append(f"{event}\n", style="white")
        else:
            timeline_text.append("No timeline events recorded.\n", style="yellow")

        return Panel(
            timeline_text,
            title="Timeline",
            border_style="cyan",
            padding=(1, 1),
        )

    def _build_findings_sections(self, context: InvestigationContext) -> list[RenderableType]:
        if not context.findings:
            return [
                Panel(
                    Text("No findings were identified during this investigation.", style="yellow"),
                    title="Findings",
                    border_style="yellow",
                    padding=(1, 1),
                )
            ]

        sections: list[RenderableType] = []
        for idx, finding in enumerate(context.findings, start=1):
            finding_text = Text()
            finding_text.append("Category:\n", style="cyan bold")
            finding_text.append(f"{finding.category or 'Unknown'}\n\n", style="white")
            finding_text.append("Title:\n", style="cyan bold")
            finding_text.append(f"{finding.title}\n\n", style="white bold")
            finding_text.append("Source:\n", style="cyan bold")
            finding_text.append(f"{finding.source or 'Unknown'}\n\n", style="white")
            finding_text.append("Confidence:\n", style="cyan bold")
            quality = self._confidence_style(finding.confidence)
            finding_text.append(f"{finding.confidence:.2f}\n\n", style=quality)
            finding_text.append("Details:\n", style="cyan bold")
            details = finding.details or "No details provided."
            for line in textwrap.wrap(details, width=76):
                finding_text.append(f"{line}\n", style="white")

            border_style = "green" if finding.confidence >= 0.75 else "yellow" if finding.confidence >= 0.45 else "red"
            sections.append(
                Panel(
                    finding_text,
                    title=f"FINDING #{idx}",
                    border_style=border_style,
                    padding=(1, 1),
                )
            )
            sections.append(Text("\n"))
        return sections

    def _build_risk_panel(self, context: InvestigationContext) -> RenderableType:
        highest_confidence = max((finding.confidence for finding in context.findings), default=0.0)
        if highest_confidence >= 0.75:
            risk_level = "HIGH"
            risk_style = "red"
            assessment = "High-risk indicators detected. Immediate follow-up and containment recommended."
        elif highest_confidence >= 0.45:
            risk_level = "MEDIUM"
            risk_style = "yellow"
            assessment = "Moderate risk observed. Validate findings and continue monitoring."
        else:
            risk_level = "LOW"
            risk_style = "green"
            assessment = "Low risk based on current evidence, but watch for emerging correlations."

        risk_text = Text()
        risk_text.append("Risk Rating:\n", style="cyan bold")
        risk_text.append(f"{risk_level}\n\n", style=f"{risk_style} bold")
        risk_text.append("Assessment:\n", style="cyan bold")
        for line in textwrap.wrap(assessment, width=76):
            risk_text.append(f"{line}\n", style="white")

        return Panel(
            risk_text,
            title="Risk Assessment",
            border_style=risk_style,
            padding=(1, 1),
        )

    def _build_correlation_panel(self, context: InvestigationContext) -> RenderableType:
        correlations = self._discover_correlations(context)
        correlation_text = Text()
        if correlations:
            correlation_text.append("Detected correlations:\n", style="cyan bold")
            for line in correlations:
                correlation_text.append(f"- {line}\n", style="white")
        else:
            correlation_text.append("No correlations identified from current findings.\n", style="yellow")

        return Panel(
            correlation_text,
            title="Correlations",
            border_style="cyan",
            padding=(1, 1),
        )

    def _build_correlation_summary_panel(self) -> RenderableType:
        summary = self.correlation_engine.get_correlation_summary()
        summary_text = Text()
        summary_text.append("Entity count: ", style="cyan bold")
        summary_text.append(f"{summary['total_entities']}\n", style="white")
        summary_text.append("Relationship count: ", style="cyan bold")
        summary_text.append(f"{summary['total_relationships']}\n", style="white")
        summary_text.append("Top correlations:\n", style="cyan bold")
        for item in summary["top_correlations"][:5]:
            summary_text.append(
                f"- {item['source']} -> {item['target']} ({item['type']}, confidence {item['confidence']:.2f})\n",
                style="white",
            )
        return Panel(
            summary_text,
            title="Correlation Summary",
            border_style="cyan",
            padding=(1, 1),
        )

    def _build_evidence_panel(self, context: InvestigationContext) -> RenderableType:
        evidence_text = Text()
        if context.findings:
            evidence_text.append("Source attribution is documented per finding.\n", style="cyan bold")
            evidence_text.append("Each finding contains the original source and confidence score.\n", style="white")
        else:
            evidence_text.append("No verifiable public evidence discovered.\n", style="yellow")
        return Panel(
            evidence_text,
            title="Evidence",
            border_style="cyan",
            padding=(1, 1),
        )

    def _build_analyst_notes_panel(self, context: InvestigationContext) -> RenderableType:
        notes = Text()
        if not context.findings:
            notes.append("No verifiable public evidence discovered. Investigation completed without source-backed findings.\n", style="yellow")
        else:
            notes.append("All findings are based on publicly accessible data sources and inferred correlations.\n", style="white")
            notes.append("Verify high-risk indicators before operational action.\n", style="white")
        return Panel(
            notes,
            title="Analyst Notes",
            border_style="cyan",
            padding=(1, 1),
        )

    def _discover_correlations(self, context: InvestigationContext) -> list[str]:
        sources = [finding.source for finding in context.findings if finding.source]
        categories = [finding.category for finding in context.findings if finding.category]
        correlations: list[str] = []
        duplicate_sources = {source for source in sources if sources.count(source) > 1}
        duplicate_categories = {category for category in categories if categories.count(category) > 1}
        if duplicate_sources:
            correlations.append(f"Repeated source references: {', '.join(sorted(duplicate_sources))}")
        if duplicate_categories:
            correlations.append(f"Multiple findings in related categories: {', '.join(sorted(duplicate_categories))}")
        if not correlations and len(context.findings) > 1:
            correlations.append("Multiple findings suggest a broader threat surface.")
        return correlations

    def _confidence_style(self, confidence: float) -> str:
        if confidence >= 0.75:
            return "green"
        if confidence >= 0.45:
            return "yellow"
        return "red"

    def action_quit(self) -> None:
        self.exit()
