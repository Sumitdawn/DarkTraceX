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
from textual.containers import Horizontal, Vertical, VerticalScroll
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
        ascii_art = "\n".join(
            [
                "DARKTRACE X",
                "Cyber Intelligence Investigation Engine",
                "Made in India | Author: Darkscripters",
            ]
        )
        banner_text = Text(ascii_art, style="bold red on black", justify="center")
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


class SummaryPanel(Static):
    summary_data: dict[str, str] = {}

    def update_summary(
        self,
        target: str,
        module: str,
        elapsed: str,
        findings_count: int,
        risk_score: str,
    ) -> None:
        self.summary_data = {
            "Target": target,
            "Module": module,
            "Investigation Time": elapsed,
            "Findings Count": str(findings_count),
            "Risk Score": risk_score,
        }
        self.refresh()

    def render(self) -> Panel:
        if not self.summary_data:
            body = Text("No investigation summary available.", style="yellow")
        else:
            table = Table.grid(expand=True)
            table.add_column(ratio=1, style="cyan bold")
            table.add_column(ratio=2, style="white")
            for label, value in self.summary_data.items():
                table.add_row(f"{label}:", value)
            body = table
        return Panel(
            body,
            title="Investigation Summary",
            border_style="green",
            padding=(1, 1),
        )


class FindingPanel(Static):
    def __init__(self, index: int, finding: Finding, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.index = index
        self.finding = finding

    def render(self) -> Panel:
        panel_text = Text()
        panel_text.append("Category: ", style="cyan bold")
        panel_text.append(f"{self.finding.category or 'Unknown'}\n", style="white")
        panel_text.append("Title: ", style="cyan bold")
        panel_text.append(f"{self.finding.title}\n", style="white bold")
        panel_text.append("Source: ", style="cyan bold")
        panel_text.append(f"{self.finding.source or 'Unknown'}\n", style="white")
        panel_text.append("Confidence: ", style="cyan bold")
        panel_text.append(f"{self.finding.confidence:.2f}\n\n", style=self._confidence_style())
        panel_text.append("Details:\n", style="cyan bold")
        details = self.finding.details or "No details provided."
        for line in textwrap.wrap(details, width=72):
            panel_text.append(f"{line}\n", style="white")

        return Panel(
            panel_text,
            title=f"Finding #{self.index}",
            border_style=self._confidence_style(),
            padding=(1, 1),
        )

    def _confidence_style(self) -> str:
        if self.finding.confidence >= 0.75:
            return "green"
        if self.finding.confidence >= 0.45:
            return "yellow"
        return "red"


class FindingsScroll(VerticalScroll):
    async def update_findings(self, findings: list[Finding]) -> None:
        self.clear()
        if not findings:
            await self.mount(
                Static(
                    "No findings identified for this investigation.",
                    style="yellow",
                )
            )
            return

        for index, finding in enumerate(findings, start=1):
            await self.mount(FindingPanel(index=index, finding=finding))


class TimelineScroll(VerticalScroll):
    async def update_timeline(self, timeline: list[str]) -> None:
        self.clear()
        if not timeline:
            await self.mount(
                Static(
                    "No timeline events recorded.",
                    style="yellow",
                )
            )
            return

        timeline_text = Text()
        for event in timeline:
            timeline_text.append("• ", style="cyan")
            timeline_text.append(f"{event}\n", style="white")
        await self.mount(Static(timeline_text))


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
                yield SummaryPanel(id="summary-panel")
                yield FindingsScroll(id="findings-scroll")
                yield TimelineScroll(id="timeline-scroll")
        yield Footer()

    async def on_mount(self) -> None:
        self.status = self.query_one(StatusPanel)
        self.summary = self.query_one(SummaryPanel)
        self.findings_scroll = self.query_one(FindingsScroll)
        self.timeline_scroll = self.query_one(TimelineScroll)
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

    async def start_investigation(self, module_name: str, target: str) -> None:
        self.active_investigations += 1
        self.update_status()
        self.status.update_status(f"Running {module_name} investigation for {target}...")
        self.summary.update_summary(
            target=target,
            module=module_name,
            elapsed="0.0s",
            findings_count=0,
            risk_score="N/A",
        )
        self.findings_scroll.clear()
        self.timeline_scroll.clear()

        handler = MODULE_MAP.get(module_name)
        if handler is None:
            self.status.update_status(f"The module '{module_name}' is currently unavailable.")
            self.active_investigations -= 1
            self.update_status()
            return

        investigation_start = datetime.now()
        try:
            results = await asyncio.to_thread(handler, target)
            context = self.investigation_engine.create(module_name, target)
            for finding in results.findings:
                self.investigation_engine.add_finding(context, finding)
            for event in results.timeline:
                self.investigation_engine.add_event(context, event)
            self.investigation_engine.record(context)
            self.correlation_engine.add_module_result(module_name, target, results)

            elapsed = datetime.now() - investigation_start
            duration = f"{elapsed.total_seconds():.1f}s"
            risk_score = self._calculate_risk_score(results.findings)

            self.summary.update_summary(
                target=target,
                module=module_name,
                elapsed=duration,
                findings_count=len(results.findings),
                risk_score=risk_score,
            )
            await self.findings_scroll.update_findings(results.findings)
            await self.timeline_scroll.update_timeline(results.timeline)

            self.status.update_status("Investigation complete. Use mouse wheel or j/k to scroll.")
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
        scrollable = self.focused if isinstance(self.focused, VerticalScroll) else self.findings_scroll
        scrollable.scroll_down()

    def action_scroll_up(self) -> None:
        scrollable = self.focused if isinstance(self.focused, VerticalScroll) else self.findings_scroll
        scrollable.scroll_up()

    def action_page_down(self) -> None:
        scrollable = self.focused if isinstance(self.focused, VerticalScroll) else self.findings_scroll
        scrollable.page_down()

    def action_page_up(self) -> None:
        scrollable = self.focused if isinstance(self.focused, VerticalScroll) else self.findings_scroll
        scrollable.page_up()

    def action_quit(self) -> None:
        self.exit()
