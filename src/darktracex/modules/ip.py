"""IP Address Intelligence Module for DarkTrace X.

Performs OSINT-grade IP analysis:
- Reverse DNS resolution
- Geolocation via public APIs
- ASN classification (Cloud, Hosting, ISP, Enterprise)
- Threat categorization
- Risk scoring based on ASN reputation
"""

from __future__ import annotations

import socket
from datetime import datetime
from ipaddress import ip_address
from ..entities import Finding, ModuleResult
from ..utils import now_iso, safe_request, round_confidence


def _classify_asn(org_string: str) -> dict:
    """Classify ASN type based on organization string."""

    org_lower = org_string.lower()

    cloud_keywords = ["aws", "amazon", "azure", "microsoft", "google cloud", "gcp", "ibm cloud", "digitalocean", "linode", "vultr"]
    hosting_keywords = ["hosting", "data center", "datacenter", "dedicated", "vps", "server", "provider", "colocation"]
    residential_keywords = ["residential", "adsl", "dsl", "cable", "broadband", "internet service"]
    enterprise_keywords = ["corporation", "corp", "enterprise", "university", "bank", "financial", "government"]

    if any(kw in org_lower for kw in cloud_keywords):
        return {
            "type": "Cloud Provider",
            "risk_delta": 0.15,
            "details": "Cloud infrastructure provider",
        }

    if any(kw in org_lower for kw in hosting_keywords):
        return {
            "type": "Hosting Provider",
            "risk_delta": 0.10,
            "details": "Commercial hosting/data center",
        }

    if any(kw in org_lower for kw in residential_keywords):
        return {
            "type": "Residential ISP",
            "risk_delta": -0.05,
            "details": "Residential Internet Service Provider",
        }

    if any(kw in org_lower for kw in enterprise_keywords):
        return {
            "type": "Enterprise/Organization",
            "risk_delta": 0.05,
            "details": "Enterprise or institutional network",
        }

    return {
        "type": "ISP/Unclassified",
        "risk_delta": 0.0,
        "details": "Commercial ISP or unclassified organization",
    }


def run_ip_intel(target: str) -> ModuleResult:
    """Run IP intelligence investigation."""

    result = ModuleResult()
    timestamp = now_iso()
    ip = target.strip()
    result.timeline.append(
        f"[{datetime.utcnow().strftime('%H:%M:%S')}] IP intelligence beginning for {ip}"
    )

    # Validate IP format
    try:
        addr = ip_address(ip)
        result.timeline.append(f"Validated IP address: {ip}")
    except ValueError:
        result.findings.append(
            Finding(
                category="Validation",
                title="Invalid IP address format",
                details=f"'{ip}' is not a valid IPv4 or IPv6 address",
                source="ipaddress",
                timestamp=timestamp,
                confidence=round_confidence(0.99),
            )
        )
        result.timeline.append("IP validation failed")
        return result

    # Reverse DNS lookup
    reverse_dns = "Unknown"
    has_reverse_dns = False
    try:
        reverse_dns = socket.gethostbyaddr(str(addr))[0]
        has_reverse_dns = True
        result.findings.append(
            Finding(
                category="Reverse DNS",
                title="Reverse DNS PTR record",
                details=reverse_dns,
                source="socket.gethostbyaddr",
                timestamp=timestamp,
                confidence=round_confidence(0.90),
            )
        )
        result.timeline.append(f"Reverse DNS resolved: {reverse_dns}")
    except (socket.herror, socket.gaierror):
        result.findings.append(
            Finding(
                category="Reverse DNS",
                title="No reverse DNS record",
                details="PTR record not found for this IP",
                source="socket.gethostbyaddr",
                timestamp=timestamp,
                confidence=round_confidence(0.85),
            )
        )
        result.timeline.append("No reverse DNS available")

    # Geolocation and ASN via ipinfo.io
    geo = safe_request(f"https://ipinfo.io/{ip}/json")

    if isinstance(geo, dict) and geo.get("ip"):
        city = geo.get("city", "Unknown")
        region = geo.get("region", "Unknown")
        country = geo.get("country", "Unknown")
        org = geo.get("org", "Unknown")

        geo_details = f"{city}, {region}, {country}"
        result.findings.append(
            Finding(
                category="Geolocation",
                title="Geographic location",
                details=geo_details,
                source="ipinfo.io",
                timestamp=timestamp,
                confidence=round_confidence(0.75),
            )
        )
        result.timeline.append(f"Geolocation: {geo_details}")

        # ASN classification
        if org and org != "Unknown":
            asn_class = _classify_asn(org)
            result.findings.append(
                Finding(
                    category="ASN Classification",
                    title=f"ASN Type: {asn_class['type']}",
                    details=f"Organization: {org}. {asn_class['details']}",
                    source="ipinfo.io + heuristic classification",
                    timestamp=timestamp,
                    confidence=round_confidence(0.80),
                )
            )
            result.timeline.append(
                f"ASN classified as: {asn_class['type']}"
            )

        # Threat categorization
        threat_cat = _categorize_threat(geo, has_reverse_dns, org)
        result.findings.append(
            Finding(
                category="Threat Assessment",
                title="Threat category",
                details=threat_cat["description"],
                source="DarkTrace X threat engine",
                timestamp=timestamp,
                confidence=round_confidence(threat_cat["confidence"]),
            )
        )
        result.timeline.append(f"Threat category: {threat_cat['category']}")

    else:
        result.timeline.append("IP geolocation lookup failed or returned no data")

    # Risk scoring
    risk_score = _calculate_risk_score(geo, has_reverse_dns)
    result.findings.append(
        Finding(
            category="Risk Scoring",
            title="IP exposure risk score",
            details=f"Risk score: {risk_score:.2f} (0.0=low, 1.0=high). "
            f"Based on: ASN type, reverse DNS presence, geolocation coverage.",
            source="DarkTrace X risk engine",
            timestamp=timestamp,
            confidence=round_confidence(0.80),
        )
    )
    result.timeline.append(f"Risk score calculated: {risk_score:.2f}")

    return result


def _categorize_threat(geo: dict, has_reverse_dns: bool, org: str) -> dict:
    """Categorize IP threat level."""

    org_lower = org.lower() if org else ""

    if "cloud" in org_lower or "aws" in org_lower or "azure" in org_lower:
        return {
            "category": "Cloud Infrastructure",
            "description": "IP belongs to cloud provider. May indicate: "
            "legitimate cloud service, compromised cloud instance, or malware hosting.",
            "confidence": 0.85,
        }

    if (
        "hosting" in org_lower
        or "datacenter" in org_lower
        or "vps" in org_lower
    ):
        return {
            "category": "Commercial Hosting",
            "description": "IP belongs to hosting provider. May indicate: "
            "legitimate hosted service, phishing site, or malware infrastructure.",
            "confidence": 0.80,
        }

    if "residential" in org_lower or "adsl" in org_lower:
        return {
            "category": "Residential Network",
            "description": "IP appears to be residential. May indicate: "
            "legitimate home user, compromised home network, or botnet node.",
            "confidence": 0.75,
        }

    # Generic assessment
    threat_desc = "IP registered to commercial provider. "
    if has_reverse_dns:
        threat_desc += (
            "Reverse DNS present (suggests legitimate infrastructure). "
        )
    else:
        threat_desc += "No reverse DNS (may indicate suspicious activity). "
    threat_desc += "Requires additional context for threat assessment."

    return {
        "category": "Unknown/Commercial",
        "description": threat_desc,
        "confidence": 0.65,
    }


def _calculate_risk_score(geo: dict, has_reverse_dns: bool) -> float:
    """Calculate risk score based on OSINT signals."""

    risk = 0.5  # Baseline neutral

    if not isinstance(geo, dict) or not geo.get("ip"):
        return round_confidence(0.55)  # Unknown IP, slightly elevated

    org = geo.get("org", "").lower()

    # Reverse DNS presence reduces risk
    if has_reverse_dns:
        risk -= 0.15
    else:
        risk += 0.05

    # Cloud/hosting classification adjusts risk
    if any(kw in org for kw in ["aws", "azure", "google", "digitalocean"]):
        risk += 0.10  # Cloud IPs can be misused
    elif any(kw in org for kw in ["residential", "adsl", "dsl"]):
        risk -= 0.05  # Residential IPs typically lower risk

    # Geographic consistency check
    if geo.get("country") and geo.get("city"):
        risk -= 0.05  # Full geolocation data present = more trustworthy

    return round_confidence(min(0.95, max(0.05, risk)))
