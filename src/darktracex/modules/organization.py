from __future__ import annotations

import socket
import dns.resolver
import ssl
import whois
from datetime import datetime
from ..entities import Finding, ModuleResult
from ..utils import now_iso, safe_request, round_confidence


def _derive_candidate_domains(org_name: str) -> list[str]:
    """Generate likely domains from organization name using heuristics."""
    candidates = []
    
    normalized = org_name.strip().lower()
    base = normalized.replace(" ", "").replace("-", "").replace(".", "")
    
    # Strategy 1: Common TLDs with normalized name
    for tld in ["com", "io", "org", "net"]:
        candidates.append(f"{base}.{tld}")
    
    # Strategy 2: First word only + common TLDs
    first_word = base.split()[0] if " " in normalized else base
    if first_word != base:
        for tld in ["com", "io", "org"]:
            candidates.append(f"{first_word}.{tld}")
    
    # Strategy 3: Known patterns for tech companies
    if "inc" not in normalized:
        candidates.append(f"{base}inc.com")
    
    # Strategy 4: Corporate patterns
    for tld in ["com", "io"]:
        candidates.append(f"{base}-corp.{tld}")
        candidates.append(f"{base}-labs.{tld}")
    
    return candidates


def _test_domain_resolves(domain: str) -> bool:
    """Test if domain has DNS A record."""
    try:
        dns.resolver.resolve(domain, "A", lifetime=5)
        return True
    except Exception:
        return False


def _get_ssl_info(hostname: str) -> dict | None:
    """Retrieve SSL certificate metadata."""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return None
                subject = dict(x[0] for x in cert.get("subject", []))
                issuer = dict(x[0] for x in cert.get("issuer", []))
                return {
                    "cn": subject.get("commonName", ""),
                    "issuer": issuer.get("commonName", ""),
                    "version": cert.get("version"),
                    "notAfter": cert.get("notAfter", "")
                }
    except Exception:
        return None


def _get_ct_entries(domain: str) -> int:
    """Query Certificate Transparency logs for domain."""
    try:
        ct_url = f"https://crt.sh/?q={domain}&output=json"
        response = safe_request(ct_url)
        if isinstance(response, list):
            return len(response)
    except Exception:
        pass
    return 0


def run_org_intel(target: str) -> ModuleResult:
    """Organization intelligence engine."""
    result = ModuleResult()
    timestamp = now_iso()
    org_name = target.strip()
    now_ts = datetime.utcnow().strftime("%H:%M:%S")
    
    result.timeline.append(f"[{now_ts}] Organization intelligence beginning for {org_name}")
    
    # Step 1: Derive candidate domains
    candidates = _derive_candidate_domains(org_name)
    result.timeline.append(f"Generated {len(candidates)} candidate domains from organization name")
    
    # Step 2: Test which domains resolve
    valid_domains = []
    for domain in candidates[:5]:  # Test top 5 candidates
        if _test_domain_resolves(domain):
            valid_domains.append(domain)
            result.timeline.append(f"Domain resolves: {domain}")
    
    if not valid_domains:
        result.findings.append(Finding(
            category="Domain Discovery",
            title="No primary domains resolved",
            details=f"Tested {len(candidates[:5])} candidate domains; none resolved. Organization may use non-standard domains or be private.",
            source="DarkTrace X domain derivation engine",
            timestamp=timestamp,
            confidence=round_confidence(0.45),
        ))
        result.timeline.append("No valid domains found")
        return result
    
    primary_domain = valid_domains[0]
    result.timeline.append(f"Using primary domain: {primary_domain}")
    
    # Step 3: WHOIS on primary domain
    try:
        whois_data = whois.whois(primary_domain)
        registrant = whois_data.get("registrant_name") or whois_data.get("admin_name") or "Private"
        registrar = whois_data.get("registrar") or "Unknown"
        created = str(whois_data.get("creation_date", "")).split()[0]
        result.findings.append(Finding(
            category="WHOIS",
            title="Primary domain registration data",
            details=f"Domain: {primary_domain} | Registrant: {registrant} | Registrar: {registrar} | Created: {created}",
            source="whois",
            timestamp=timestamp,
            confidence=round_confidence(0.88),
        ))
        result.timeline.append("Collected WHOIS data for primary domain")
    except Exception as exc:
        result.findings.append(Finding(
            category="WHOIS",
            title="WHOIS lookup failed",
            details=str(exc),
            source="whois",
            timestamp=timestamp,
            confidence=round_confidence(0.15),
        ))
        result.timeline.append("WHOIS lookup failed")
    
    # Step 4: DNS records
    dns_records = {}
    for rtype in ["A", "AAAA", "MX", "NS", "TXT", "SOA"]:
        try:
            answers = dns.resolver.resolve(primary_domain, rtype, lifetime=10)
            dns_records[rtype] = [r.to_text() for r in answers]
        except Exception:
            dns_records[rtype] = []
    
    dns_summary = ", ".join(f"{k}={len(v)}" for k, v in dns_records.items() if v)
    result.findings.append(Finding(
        category="DNS Records",
        title="Primary domain DNS infrastructure",
        details=dns_summary,
        source="dns.resolver",
        timestamp=timestamp,
        confidence=round_confidence(0.85),
    ))
    result.timeline.append("Collected DNS records")
    
    # Step 5: SSL certificate analysis
    ssl_info = _get_ssl_info(primary_domain)
    if ssl_info:
        result.findings.append(Finding(
            category="SSL Certificate",
            title="Primary domain SSL certificate metadata",
            details=f"CN: {ssl_info.get('cn')} | Issuer: {ssl_info.get('issuer')} | Expires: {ssl_info.get('notAfter')}",
            source="ssl",
            timestamp=timestamp,
            confidence=round_confidence(0.82),
        ))
        result.timeline.append("Retrieved SSL certificate info")
    else:
        result.timeline.append("SSL certificate retrieval failed or not available")
    
    # Step 6: Certificate Transparency data
    ct_count = _get_ct_entries(primary_domain)
    result.findings.append(Finding(
        category="Certificate Transparency",
        title="Public certificate history",
        details=f"Found {ct_count} certificate entries in CT logs for {primary_domain}",
        source="crt.sh",
        timestamp=timestamp,
        confidence=round_confidence(0.75 if ct_count > 0 else 0.35),
    ))
    result.timeline.append(f"Queried CT logs: {ct_count} entries found")
    
    # Step 7: Subdomain discovery via CT
    subdomains = set()
    if ct_count > 0:
        try:
            ct_url = f"https://crt.sh/?q={primary_domain}&output=json"
            ct_response = safe_request(ct_url)
            if isinstance(ct_response, list):
                for entry in ct_response[:50]:
                    if isinstance(entry, dict):
                        names = entry.get("name_value", "").split("\n")
                        for name in names:
                            if name.strip() and name.strip() not in [primary_domain, f"*.{primary_domain}"]:
                                subdomains.add(name.strip())
        except Exception:
            pass
    
    if subdomains:
        result.findings.append(Finding(
            category="Subdomain Discovery",
            title="Public subdomains identified",
            details=f"Discovered {len(subdomains)} unique subdomains: {', '.join(list(subdomains)[:5])}{'...' if len(subdomains) > 5 else ''}",
            source="crt.sh",
            timestamp=timestamp,
            confidence=round_confidence(0.8),
        ))
        result.timeline.append(f"Identified {len(subdomains)} subdomains")
    
    # Step 8: Public footprint via search
    search_query = f'site:{primary_domain} OR "{org_name}"'
    search_encoded = search_query.replace(" ", "+")
    search = safe_request("https://api.allorigins.win/raw", params={"url": f"https://www.bing.com/search?q={search_encoded}"})
    if search:
        result.findings.append(Finding(
            category="Public Footprint",
            title="Organization public web presence",
            details=f"Public search results indicate active web presence for {primary_domain}",
            source="https://api.allorigins.win",
            timestamp=timestamp,
            confidence=round_confidence(0.65),
        ))
        result.timeline.append("Collected public search references")
    
    # Step 9: Risk scoring
    risk_score = 0.4
    
    if valid_domains:
        risk_score += 0.15  # Resolvable domain = higher visibility
    
    if ssl_info:
        risk_score += 0.1  # Valid SSL = operational presence
    
    if ct_count > 5:
        risk_score += 0.1  # Many certificates = public activity
    
    if len(subdomains) > 3:
        risk_score += 0.1  # Multiple subdomains = larger attack surface
    
    risk_score = min(1.0, risk_score)
    
    result.findings.append(Finding(
        category="Exposure Risk",
        title="Organization exposure and attack surface score",
        details=f"Risk score: {risk_score:.2f}. Factors: {len(valid_domains)} active domains, {ct_count} certificates, {len(subdomains)} subdomains.",
        source="DarkTrace X risk engine",
        timestamp=timestamp,
        confidence=round_confidence(0.8),
    ))
    result.timeline.append("Calculated organizational risk score")
    
    return result
