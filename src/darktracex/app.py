from __future__ import annotations

import asyncio
import logging
import textwrap
from datetime import datetime
from typing import Any

import textual
from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, RichLog, Static

from .config import AppConfig
from .core.correlation import CorrelationEngine
from .db import init_db, SessionLocal
from .entities import Finding, InvestigationContext, ModuleResult
from .investigation import InvestigationEngine
from .modules import phone, email, domain, ip, organization, username
from .plugin_manager import PluginRegistry
from .reports import ReportEngine
from .utils import valid_email, valid_phone
import ipaddress

MENU_ITEMS = [
    "New Investigation",
    "Cases",
    "Dashboard",
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

# Modules to run automatically depending on detected primary type
AUTO_MODULES = {
    "Email Address": ["Email Address", "Domain", "Organization", "Social Profile"],
    "Domain": ["Domain", "IP Address", "Organization"],
    "IP Address": ["IP Address", "Domain"],
    "Phone Number": ["Phone Number"],
    "Organization": ["Organization", "Domain", "Email Address"],
    "Social Profile": ["Social Profile", "Domain", "Email Address"],
}


class Banner(Static):
    def render(self) -> Panel:
        width = self.size.width or 80
        title = "DARKTRACEX"
        origin = "MADE IN INDIA"
        author = "Author: Darkscripters™"

        if width < 50:
            lines = [title, origin, author]
        elif width < 80:
            lines = [title, origin, author]
        else:
            lines = [title, origin, author]

        banner_text = Text("\n".join(lines), style="bold red on black", justify="center")
        return Panel(
            banner_text,
            border_style="bright_cyan",
            style="on black",
            padding=(0, 1),
            expand=False,
        )


class StatusPanel(Static):
    status_text = reactive("Ready. Select a module and enter a target.")

    def update_status(self, content: str) -> None:
        self.status_text = content
        self.refresh()

    def render(self) -> Panel:
        return Panel(
            self.status_text,
            title="Status",
            border_style="green",
            padding=(1, 1),
        )


class DarkTraceXApp(App):
    CSS_PATH = "darktracex.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("j", "scroll_down", "Scroll Down"),
        ("k", "scroll_up", "Scroll Up"),
        ("pgdown", "page_down", "Page Down"),
        ("pgup", "page_up", "Page Up"),
    ]

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
        yield Banner(id="banner")
        with Horizontal():
            with Vertical(id="left-pane"):
                yield Static("Main Menu", id="menu-title")
                menu_items = []
                for item in MENU_ITEMS:
                    row = ListItem(Label(item))
                    row.module_name = item
                    menu_items.append(row)
                yield ListView(*menu_items, id="menu-list")
                yield Input(placeholder="Enter target and press Enter", id="target-input")
                yield Button("Run Investigation", id="run-button", variant="primary")
                yield StatusPanel(id="status-panel")
            with Vertical(id="right-pane"):
                yield RichLog(id="output-panel", highlight=True, markup=True, wrap=True)
        yield Footer()

    async def on_mount(self) -> None:
        self.status = self.query_one(StatusPanel)
        self.output = self.query_one("#output-panel", RichLog)
        self.update_header()

        try:
            loaded_plugins = self.plugin_registry.load()
            self.logger.info("Loaded %d plugins", len(loaded_plugins))
        except Exception as exc:
            self.logger.exception("Plugin loading failed")
            self.status.update_status(f"Plugin loading failed: {exc}")

        self.update_status()

    def update_header(self) -> None:
        self.query_one(Header).sub_title = f"Workspace: {self.current_workspace} | Plugins: {len(self.plugin_registry.active)}"

    def update_status(self) -> None:
        self.status.update_status(
            f"Module: {self.selected_module}\nActive Investigations: {self.active_investigations}\nLoaded Plugins: {len(self.plugin_registry.active)}"
        )

    def display_results(self, formatted: str) -> None:
        self.output.clear()
        for line in formatted.splitlines():
            self.output.write(line)
        self.output.scroll_end(animate=False)

    def format_results(self, context: InvestigationContext, duration: str, risk_score: str) -> str:
        lines: list[str] = []
        separator = "# " + "=" * 48
        lines.append(separator)
        lines.append("INVESTIGATION SUMMARY")
        lines.append(f"Target: {context.target}")
        lines.append(f"Module: {context.entity_type}")
        lines.append(f"Investigation Time: {duration}")
        lines.append(f"Findings Count: {len(context.findings)}")
        lines.append(f"Risk Score: {risk_score}")
        if context.investigation_id:
            lines.append(f"Investigation ID: {context.investigation_id}")

        case_risk = context.metadata.get("case_risk", {})
        if case_risk:
            lines.append(f"Case Risk Level: {case_risk.get('risk_level', 'N/A')}")
            lines.append(f"Correlation Density: {case_risk.get('relationship_density', 0.0):.2f}")
            lines.append(f"Entity Confidence: {case_risk.get('entity_confidence', 0.0):.2f}")
            lines.append(f"Relationship Confidence: {case_risk.get('relationship_confidence', 0.0):.2f}")
        lines.append("")
        lines.append(separator)
        lines.append("TIMELINE")
        if context.timeline:
            for event in context.timeline:
                lines.append(f"{event}")
        else:
            lines.append("No timeline events recorded.")
        lines.append("")
        lines.append(separator)
        lines.append("CASE INSIGHTS")
        if context.leads:
            for lead in context.leads:
                lines.append(f"- [{lead.confidence:.2f}] {lead.title}")
                lines.append(f"  Target: {lead.target}")
                lines.append(f"  {lead.description}")
        else:
            lines.append("No recommended leads could be generated from this investigation.")
        lines.append("")
        lines.append(separator)
        lines.append("FINDINGS")
        if context.findings:
            for idx, finding in enumerate(context.findings, start=1):
                lines.append(f"[{idx}] {finding.title}")
                lines.append(f"Category: {finding.category or 'Unknown'}")
                lines.append(f"Source: {finding.source or 'Unknown'}")
                lines.append(f"Confidence: {finding.confidence:.2f}")
                lines.append("Details:")
                details = finding.details or "No details provided."
                for detail_line in details.splitlines():
                    lines.append(f"{detail_line}")
                if idx < len(context.findings):
                    lines.append("---")
        else:
            lines.append("No findings identified during this investigation.")
        lines.append("")
        lines.append(separator)
        lines.append("CORRELATION DATA")
        correlations = self._discover_correlations(context)
        if correlations:
            for item in correlations:
                lines.append(f"- {item}")
        else:
            lines.append("No correlations identified from current findings.")
        lines.append("")
        lines.append(separator)
        lines.append("RISK ASSESSMENT")
        lines.append(f"Risk Score: {risk_score}")
        if case_risk:
            lines.append(f"Case Risk Level: {case_risk.get('risk_level', 'N/A')}")
        return "\n".join(lines)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.selected_module = getattr(event.item, "module_name", "")
        self.status.update_status(f"Selected {self.selected_module}. Enter target and run investigation.")
        self.update_header()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-button":
            target_input = self.query_one(Input)
            target = target_input.value.strip()
            if not target:
                self.status.update_status("Please enter a valid target before running an investigation.")
                return
            if self.selected_module == "Exit":
                self.exit()
                return
            asyncio.create_task(self.start_investigation(self.selected_module, target))

        def _determine_primary_module(self, target: str) -> str:
            """Detect the primary module for a given target string."""
            t = target.strip()
            if valid_email(t):
                return "Email Address"
            if valid_phone(t):
                return "Phone Number"
            try:
                _ = ipaddress.ip_address(t)
                return "IP Address"
            except Exception:
                pass
            # domain-like
            if "." in t and len(t) > 3:
                return "Domain"
            # heuristics: organization (contains space and letters)
            if " " in t and len(t.split()) <= 4:
                return "Organization"
            # fallback to username/profile
            return "Social Profile"

        async def _run_auto_modules(self, target: str) -> ModuleResult:
            """Run a set of modules automatically based on detected target type and aggregate results."""
            primary = self._determine_primary_module(target)
            modules = AUTO_MODULES.get(primary, [primary])
            aggregated = ModuleResult()
            for mod_name in modules:
                handler = MODULE_MAP.get(mod_name)
                if handler is None:
                    continue
                try:
                    res = await asyncio.to_thread(handler, target)
                except Exception:
                    continue
                # ingest for correlation as well
                self.correlation_engine.add_module_result(mod_name, target, res)
                # aggregate findings and timeline
                aggregated.findings.extend(res.findings)
                aggregated.timeline.extend(res.timeline)
            return aggregated

    async def start_investigation(self, module_name: str, target: str) -> None:
        self.active_investigations += 1
        self.update_status()
        self.status.update_status(f"Running {module_name} investigation for {target}...")
        self.output.clear()

        investigation_start = datetime.now()
        try:
            self.correlation_engine.reset()
            # Auto-run orchestration when user chooses New Investigation
            if module_name == "New Investigation":
                results = await self._run_auto_modules(target)
                primary = self._determine_primary_module(target)
                context = self.investigation_engine.create(primary, target)
            else:
                handler = MODULE_MAP.get(module_name)
                if handler is None:
                    self.status.update_status(f"The module '{module_name}' is currently unavailable.")
                    self.active_investigations -= 1
                    self.update_status()
                    return
                results = await asyncio.to_thread(handler, target)
                context = self.investigation_engine.create(module_name, target)

            for finding in results.findings:
                self.investigation_engine.add_finding(context, finding)
            for event in results.timeline:
                self.investigation_engine.add_event(context, event)
            self.investigation_engine.record(context)

            # If not already added to the correlation engine by auto-run, add single module result
            if module_name != "New Investigation":
                self.correlation_engine.add_module_result(module_name, target, results)

            context.metadata["correlation_summary"] = self.correlation_engine.get_correlation_summary()
            context.metadata["case_risk"] = self.correlation_engine.get_case_risk()
            for lead in self.correlation_engine.get_recommended_leads():
                context.add_lead(lead)

            elapsed = datetime.now() - investigation_start
            duration = f"{elapsed.total_seconds():.1f}s"
            risk_score = self._calculate_risk_score(results.findings)

            self.status.update_status("Investigation complete. Formatting output...")
            formatted = self.format_results(context, duration, risk_score)
            self.display_results(formatted)

            sources = sorted({finding.source for finding in context.findings if finding.source})
            summary_text = (
                "Executive summary synthesized from investigation findings, correlation analysis, "
                "and actionable lead generation."
            )
            try:
                self.report_engine.generate_json(
                    context.investigation_id,
                    summary_text,
                    context.findings,
                    context.timeline,
                    sources,
                    metadata=context.metadata,
                    correlation=context.metadata.get("correlation_summary", {}),
                    leads=context.leads,
                )
                self.report_engine.generate_html(
                    context.investigation_id,
                    summary_text,
                    context.findings,
                    context.timeline,
                    sources,
                    metadata=context.metadata,
                    correlation=context.metadata.get("correlation_summary", {}),
                    leads=context.leads,
                )
                self.status.update_status(
                    "Investigation complete. Reports generated and output displayed. Scroll with mouse wheel or k/j."
                )
            except Exception as report_exc:
                self.logger.exception("Report generation failed")
                self.status.update_status(
                    f"Investigation complete. Report generation failed: {report_exc}"
                )
        except Exception as exc:
            self.logger.exception("Investigation error")
            self.status.update_status(f"Investigation error: {exc}")
        finally:
            self.active_investigations -= 1
            self.update_status()

    def _calculate_risk_score(self, findings: list[Finding]) -> str:
        if not findings:
            return "N/A"
        confidence = max((finding.confidence for finding in findings), default=0.0)
        if confidence >= 0.75:
            return "HIGH"
        if confidence >= 0.45:
            return "MEDIUM"
        return "LOW"

    def action_scroll_down(self) -> None:
        self.output.scroll_down()

    def action_scroll_up(self) -> None:
        self.output.scroll_up()

    def action_page_down(self) -> None:
        self.output.page_down()

    def action_page_up(self) -> None:
        self.output.page_up()

    def action_quit(self) -> None:
        self.exit()

    def _discover_correlations(self, context: InvestigationContext) -> list[str]:
        """Discover correlations from the internal correlation engine summary."""
        summary = context.metadata.get("correlation_summary", {})
        correlations: list[str] = []

        for item in summary.get("top_correlations", [])[:5]:
            correlations.append(
                f"{item['source']} -> {item['target']} ({item['type']}, confidence {item['confidence']:.2f})"
            )

        if not correlations and summary.get("total_relationships", 0) > 0:
            correlations.append("Correlation graph identifies relationships, but no high-confidence top links were surfaced.")
        if not correlations and len(context.findings) > 1:
            correlations.append("Multiple findings suggest a broader threat surface.")

        return correlations
