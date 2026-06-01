from __future__ import annotations

import ssl
import socket
import re
import whois
import dns.resolver
from datetime import datetime
from ..entities import Finding, ModuleResult
from ..utils import now_iso, safe_request, round_confidence


def _get_ssl_info(hostname: str) -> str:
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                subject = dict(x[0] for x in cert.get("subject", []))
                issuer = dict(x[0] for x in cert.get("issuer", []))
                return f"Subject: {subject.get('commonName')} Issuer: {issuer.get('commonName')}"
    except Exception as exc:
        return f"SSL retrieval failed: {exc}"


def _parse_crt_sh(domain: str) -> str:
    query = f"https://crt.sh/?q=%25.{domain}&output=json"
    payload = safe_request(query)
    if isinstance(payload, list):
        issuers = {item.get("issuer_name") for item in payload if isinstance(item, dict)}
        return f"Certificate Transparency entries: {len(payload)} issuers: {', '.join(list(issuers)[:3])}"
    return "Certificate transparency feed unavailable"


def run_domain_intel(target: str) -> ModuleResult:
    result = ModuleResult()
    timestamp = now_iso()
    domain = target.strip().lower()
    result.timeline.append(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Domain intelligence beginning for {domain}")

    try:
        whois_data = whois.whois(domain)
        result.findings.append(Finding(
            category="WHOIS",
            title="Domain registration and ownership data",
            details=f"Registrar: {whois_data.get('registrar')} | Creation date: {whois_data.get('creation_date')}",
            source="whois",
            timestamp=timestamp,
            confidence=round_confidence(0.82),
        ))
        result.timeline.append("Collected WHOIS data")
    except Exception as exc:
        result.findings.append(Finding(
            category="WHOIS",
            title="WHOIS lookup failed",
            details=str(exc),
            source="whois",
            timestamp=timestamp,
            confidence=round_confidence(0.2),
        ))
        result.timeline.append("WHOIS lookup failed")

    records = {}
    for record_type in ["A", "AAAA", "MX", "NS", "TXT", "SOA"]:
        try:
            answers = dns.resolver.resolve(domain, record_type, lifetime=10)
            records[record_type] = [r.to_text() for r in answers]
        except Exception:
            records[record_type] = []
    result.findings.append(Finding(
        category="DNS Records",
        title="Domain DNS records",
        details=", ".join(f"{key}={records[key]}" for key in records if records[key]),
        source="dns.resolver",
        timestamp=timestamp,
        confidence=round_confidence(0.85),
    ))
    result.timeline.append("Collected DNS records")

    ssl_info = _get_ssl_info(domain)
    result.findings.append(Finding(
        category="SSL Certificate",
        title="SSL certificate metadata",
        details=ssl_info,
        source="ssl",
        timestamp=timestamp,
        confidence=round_confidence(0.75),
    ))
    result.timeline.append("Retrieved SSL certificate information")

    ct = _parse_crt_sh(domain)
    result.findings.append(Finding(
        category="Certificate Transparency",
        title="Public certificate history",
        details=ct,
        source="crt.sh",
        timestamp=timestamp,
        confidence=round_confidence(0.68),
    ))
    result.timeline.append("Queried certificate transparency logs")

    search = safe_request("https://api.allorigins.win/raw", params={"url": f"https://www.bing.com/search?q={domain}"})
    if search:
        result.findings.append(Finding(
            category="Public References",
            title="Domain publicly indexed references",
            details="Search hits retrieved from Bing via proxy.",
            source="https://api.allorigins.win",
            timestamp=timestamp,
            confidence=round_confidence(0.62),
        ))
        result.timeline.append("Collected public domain references")

    score = 0.5 + (0.1 if records.get("A") else 0) + (0.1 if "crt.sh" in ct else 0)
    result.findings.append(Finding(
        category="Exposure Risk",
        title="Domain exposure risk score",
        details="Combined exposure score based on DNS, certificate transparency, and public visibility.",
        source="DarkTrace X risk engine",
        timestamp=timestamp,
        confidence=round_confidence(score),
    ))
    result.timeline.append("Calculated exposure risk")
    return result
