from __future__ import annotations

from datetime import datetime
from typing import Sequence


class TimelineEngine:
    def __init__(self) -> None:
        self.events: list[str] = []

    def add(self, message: str) -> None:
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        self.events.append(f"[{timestamp}] {message}")

    def export(self) -> list[str]:
        return self.events.copy()

    def render(self, width: int = 80) -> str:
        return "\n".join(self.events)
