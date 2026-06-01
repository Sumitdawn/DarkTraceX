from __future__ import annotations

import re
import requests
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from .models import Investigation

USER_AGENT = "DarkTraceX/0.1 (+https://darktracex.local)"
PHONE_REGEX = re.compile(r"^\+?[0-9]{7,20}$")
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_request(url: str, params: dict | None = None, timeout: int = 15) -> dict | str | None:
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text
    except requests.RequestException:
        return None


def normalize_target(target: str) -> str:
    return target.strip()


def round_confidence(value: float) -> float:
    return max(0.0, min(1.0, round(value, 2)))


def generate_investigation_id(session: Session) -> str:
    count = session.query(Investigation).count()
    next_index = int(count) + 1
    year = datetime.utcnow().year
    return f"INV-{year}-{next_index:04d}"


def valid_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))


def valid_phone(number: str) -> bool:
    return bool(PHONE_REGEX.match(number))
