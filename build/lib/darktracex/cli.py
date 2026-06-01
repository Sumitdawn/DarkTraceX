from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from .app import DarkTraceXApp
from .config import AppConfig
from .db import init_db

app = typer.Typer()
console = Console()


@app.command()
def version() -> None:
    """Display DarkTrace X version information."""
    from . import __version__
    console.print(Panel(f"DarkTrace X {__version__}\nPython CLI Intelligence OS", title="Version"))


@app.command()
def init() -> None:
    """Initialize configuration and database."""
    config = AppConfig.bootstrap()
    init_db()
    console.print(Panel("Configuration initialized and database created.", title="DarkTrace X Setup"))


@app.command()
def run() -> None:
    """Launch the DarkTrace X terminal interface."""
    config = AppConfig.bootstrap()
    init_db()
    DarkTraceXApp(config=config).run()


def main() -> None:
    app()  # type: ignore
