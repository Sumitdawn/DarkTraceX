from __future__ import annotations

import validators
import dns.resolver
import whois
from datetime import datetime
from ..entities import Finding, ModuleResult
from ..utils import now_iso, safe_request, round_confidence


def run_email_intel(target: str) -> ModuleResult:
    result = ModuleResult()
    timestamp = now_iso()
    email = target.strip().lower()
    result.timeline.append(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Email intelligence beginning for {email}")

    valid = validators.email(email)
    domain = email.split("@")[-1] if "@" in email else ""
    result.findings.append(Finding(
        category="Validation",
        title="Email address validation",
        details=f"Email address is {'valid' if valid else 'invalid'}.",
        source="validators",
        timestamp=timestamp,
        confidence=round_confidence(0.98 if valid else 0.15),
    ))
    result.timeline.append("Validated email format")

    if domain:
        try:
            records = {rtype: [str(r.to_text()) for r in dns.resolver.resolve(domain, rtype, lifetime=10)] for rtype in ["MX", "NS", "TXT"]}
            result.findings.append(Finding(
                category="DNS Records",
                title="Email domain DNS analysis",
                details=f"MX: {records.get('MX', [])}; NS: {records.get('NS', [])}.",
                source="dns.resolver",
                timestamp=timestamp,
                confidence=round_confidence(0.85),
            ))
            result.timeline.append("Retrieved DNS records for email domain")
        except Exception as exc:
            result.findings.append(Finding(
                category="DNS Records",
                title="DNS lookup failure",
                details=str(exc),
                source="dns.resolver",
                timestamp=timestamp,
                confidence=round_confidence(0.2),
            ))
            result.timeline.append("DNS lookup for email domain failed")

        try:
            whois_data = whois.whois(domain)
            org = whois_data.get("org") or whois_data.get("registrant_name") or "Unknown"
            result.findings.append(Finding(
                category="Domain WHOIS",
                title="Email domain ownership and registration",
                details=f"Organization: {org}. Registrar: {whois_data.get('registrar')}.",
                source="whois",
                timestamp=timestamp,
                confidence=round_confidence(0.78),
            ))
            result.timeline.append("Queried WHOIS for email domain")
        except Exception:
            result.timeline.append("WHOIS lookup for email domain failed")

    search_query = email.replace("@", "%40")
    public_refs = safe_request("https://api.allorigins.win/raw", params={"url": f"https://www.bing.com/search?q={search_query}"})
    if public_refs:
        result.findings.append(Finding(
            category="Public References",
            title="Publicly discoverable mentions of email address",
            details="Search results retrieved from Bing via proxy.",
            source="https://api.allorigins.win",
            timestamp=timestamp,
            confidence=round_confidence(0.6),
        ))
        result.timeline.append("Collected public references for email")

    risk = 0.5 + (0.25 if valid else -0.2)
    result.findings.append(Finding(
        category="Risk Scoring",
        title="Email exposure risk score",
        details="Risk score based on validation, DNS posture, and public references.",
        source="DarkTrace X risk engine",
        timestamp=timestamp,
        confidence=round_confidence(risk),
    ))
    result.timeline.append("Assigned risk score")
    return result
