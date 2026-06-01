from __future__ import annotations

import asyncio
from pathlib import Path
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from .config import AppConfig
from .db import init_db
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
        # Aggressive cyber-intelligence ASCII art banner
        banner_text = Text()
        
        # ASCII art header
        ascii_art = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║            ██████╗  █████╗ ██████╗ ██╗  ██╗████████╗██████╗  ║
║            ██╔══██╗██╔══██╗██╔══██╗██║ ██╔╝╚══██╔══╝██╔══██╗ ║
║            ██║  ██║███████║██████╔╝█████╔╝    ██║   ██████╔╝ ║
║            ██║  ██║██╔══██║██╔══██╗██╔═██╗    ██║   ██╔══██╗ ║
║            ██████╔╝██║  ██║██║  ██║██║  ██╗   ██║   ██║  ██║ ║
║            ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ║
║                                                               ║
║                          X                                   ║
║                                                               ║
║             CYBER INTELLIGENCE INVESTIGATION ENGINE           ║
║                                                               ║
║          [ SYSTEM INITIALIZING... DARKTRACE X ONLINE ]        ║
║                                                               ║
║           OSINT • Forensics • Threat Analysis • Recon         ║
║                                                               ║
║                    🔴 MADE IN INDIA 🔴                        ║
║                  Author: Darkscripters™                       ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
        """
        
        banner_text.append(ascii_art, style="bold red on black")
        
        return Panel(
            banner_text,
            border_style="bold bright_cyan",
            style="on black",
            expand=False,
        )


class StatusPanel(Static):
    status_text = reactive("Initializing...")

    def update_status(self, content: str) -> None:
        self.status_text = content
        self.refresh()

    def render(self) -> Panel:
        return Panel(self.status_text, title="Status", border_style="green")


class OutputPanel(Static):
    output_text = reactive("Ready. Select a module to investigate.")

    def update_output(self, content: str) -> None:
        self.output_text = content
        self.refresh()

    def render(self) -> Panel:
        return Panel(self.output_text, title="Investigation Output", border_style="bright_magenta")


class DarkTraceXApp(App):
    CSS_PATH = None
    BINDINGS = [("q", "quit","Quit")]

    selected_module = reactive("Phone Number")
    current_workspace = reactive("")
    active_investigations = reactive(0)

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.session = None
        self.plugin_registry = PluginRegistry(config)
        self.current_workspace = str(config.workspace_dir)
        self.report_engine = ReportEngine(config.workspace_dir)
        init_db()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Banner()
        with Horizontal():
            with Vertical(id="left-pane"):
                yield Static("Main Menu", id="menu-title")
                list_view = ListView(*[ListItem(Label(item)) for item in MENU_ITEMS], id="menu-list")
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
        self.plugin_registry.load()
        self.update_status()

    def update_header(self) -> None:
        self.query_one(Header).sub_title = f"Workspace: {self.current_workspace} | Plugins: {len(self.plugin_registry.active)}"

    def update_status(self) -> None:
        self.status.update_status(
            f"Module: {self.selected_module}\nActive Investigations: {self.active_investigations}\nLoaded Plugins: {len(self.plugin_registry.active)}"
        )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self.selected_module = event.item.renderable.renderable
        self.output.update_output(f"Selected module: {self.selected_module}. Enter a target and run investigation.")
        self.update_status()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-button":
            target_input = self.query_one(Input)
            target = target_input.value.strip()
            if not target:
                self.output.update_output("Please enter a valid target before running an investigation.")
                return
            if self.selected_module == "Exit":
                self.exit()
                return
            asyncio.create_task(self.start_investigation(self.selected_module, target))

    async def start_investigation(self, module_name: str, target: str) -> None:
        self.active_investigations += 1
        self.update_status()
        self.output.update_output(f"Starting {module_name} investigation for {target}...")
        self.status.update_status("Collecting intelligence...")
        await asyncio.sleep(0.1)

        handler = MODULE_MAP.get(module_name)
        if handler is None:
            self.output.update_output(f"The module '{module_name}' is currently unavailable.")
            self.active_investigations -= 1
            self.update_status()
            return

        results = await asyncio.to_thread(handler, target)
        context = InvestigationContext(investigation_id="", entity_type=module_name, target=target)
        for finding in results.findings:
            context.findings.append(finding)
        for event in results.timeline:
            context.timeline.append(event)

        formatted = self.format_results(context)
        self.output.update_output(formatted)
        self.status.update_status("Investigation complete. Generate a report from the reports menu.")
        self.active_investigations -= 1
        self.update_status()

    def format_results(self, context: InvestigationContext) -> str:
        lines = [f"Investigation: {context.entity_type} -> {context.target}"]
        lines.extend(context.timeline)
        lines.append("\nFindings:")
        for finding in context.findings:
            lines.append(f"- {finding.title} [{finding.source}] Confidence: {finding.confidence}")
            lines.append(f"  {finding.details}")
        return "\n".join(lines)

    def action_quit(self) -> None:
        self.exit()
