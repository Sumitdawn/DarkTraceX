from __future__ import annotations

import requests
from datetime import datetime
from ..entities import Finding, ModuleResult
from ..utils import now_iso, safe_request, round_confidence

# Platform enumeration targets with URL patterns
PLATFORMS = {
    "GitHub": {
        "url": "https://github.com/{username}",
        "exists_code": 200,
        "not_found_code": 404,
    },
    "Reddit": {
        "url": "https://www.reddit.com/user/{username}",
        "exists_code": 200,
        "not_found_code": 404,
    },
    "Twitter": {
        "url": "https://twitter.com/{username}",
        "exists_code": 200,
        "not_found_code": 404,
    },
    "Instagram": {
        "url": "https://www.instagram.com/{username}/",
        "exists_code": 200,
        "not_found_code": 404,
    },
    "TikTok": {
        "url": "https://www.tiktok.com/@{username}",
        "exists_code": 200,
        "not_found_code": 404,
    },
    "Medium": {
        "url": "https://medium.com/@{username}",
        "exists_code": 200,
        "not_found_code": 404,
    },
    "Pinterest": {
        "url": "https://www.pinterest.com/{username}/",
        "exists_code": 200,
        "not_found_code": 404,
    },
}


def _check_platform(platform_name: str, url: str) -> dict:
    """Check if username exists on a platform via HTTP status code."""
    headers = {
        "User-Agent": "DarkTraceX/0.1 (+https://darktracex.local)",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        status = response.status_code
        
        if status == 200:
            return {"platform": platform_name, "status": "EXISTS", "code": status}
        elif status == 404:
            return {"platform": platform_name, "status": "NOT_FOUND", "code": status}
        elif status in [301, 302, 307, 308]:
            return {"platform": platform_name, "status": "REDIRECT", "code": status}
        elif status in [403, 429]:
            return {"platform": platform_name, "status": "BLOCKED", "code": status}
        else:
            return {"platform": platform_name, "status": "UNKNOWN", "code": status}
    except requests.Timeout:
        return {"platform": platform_name, "status": "TIMEOUT", "code": None}
    except Exception as exc:
        return {"platform": platform_name, "status": "ERROR", "code": None, "error": str(exc)}


def _generate_variations(username: str) -> list[str]:
    """Generate username variations to check."""
    base = username.strip().lower()
    variations = []
    
    # Variation 1: Add common numbers
    variations.append(f"{base}123")
    
    # Variation 2: Official/dev suffix
    variations.append(f"{base}_official")
    variations.append(f"{base}.dev")
    
    # Variation 3: Prefix variations
    variations.append(f"real{base}")
    variations.append(f"i_am_{base}")
    
    # Return top 3 unique variations
    return list(set(variations))[:3]


def run_username_intel(target: str) -> ModuleResult:
    """Username intelligence and multi-platform enumeration engine."""
    result = ModuleResult()
    timestamp = now_iso()
    username = target.strip().lower()
    now_ts = datetime.utcnow().strftime("%H:%M:%S")
    
    result.timeline.append(f"[{now_ts}] Username intelligence beginning for {username}")
    result.timeline.append("Starting multi-platform enumeration")
    
    # Step 1: Primary platform enumeration
    platform_results = []
    found_platforms = []
    blocked_platforms = []
    
    for platform_name, config in PLATFORMS.items():
        url = config["url"].format(username=username)
        check_result = _check_platform(platform_name, url)
        platform_results.append(check_result)
        
        if check_result["status"] == "EXISTS":
            found_platforms.append(platform_name)
            result.timeline.append(f"✓ Username found on {platform_name}")
        elif check_result["status"] == "BLOCKED":
            blocked_platforms.append(platform_name)
            result.timeline.append(f"⚠ {platform_name} blocked/rate-limited")
        elif check_result["status"] == "NOT_FOUND":
            result.timeline.append(f"✗ Username not found on {platform_name}")
    
    # Step 2: Generate findings from platform enumeration
    if found_platforms:
        confidence = min(0.95, 0.7 + (len(found_platforms) * 0.05))
        result.findings.append(Finding(
            category="Profile Discovery",
            title="Username profiles found on public platforms",
            details=f"Identified on: {', '.join(found_platforms)} ({len(found_platforms)} platform(s))",
            source="Direct HTTP enumeration",
            timestamp=timestamp,
            confidence=round_confidence(confidence),
        ))
        result.timeline.append(f"Profile exists on {len(found_platforms)} platform(s)")
    else:
        result.findings.append(Finding(
            category="Profile Discovery",
            title="Username not found on primary platforms",
            details=f"Checked {len(PLATFORMS)} major platforms; no profiles detected.",
            source="Direct HTTP enumeration",
            timestamp=timestamp,
            confidence=round_confidence(0.2),
        ))
        result.timeline.append("No primary platform profiles detected")
    
    # Step 3: Test username variations
    result.timeline.append("Testing username variations")
    variations = _generate_variations(username)
    variation_results = {}
    
    for variation in variations:
        variation_hits = []
        for platform_name, config in PLATFORMS.items():
            url = config["url"].format(username=variation)
            check_result = _check_platform(platform_name, url)
            if check_result["status"] == "EXISTS":
                variation_hits.append(platform_name)
        
        if variation_hits:
            variation_results[variation] = variation_hits
            result.timeline.append(f"Variation '{variation}' found on: {', '.join(variation_hits)}")
    
    if variation_results:
        var_summary = "; ".join([f"{v}: {', '.join(p)}" for v, p in variation_results.items()])
        result.findings.append(Finding(
            category="Username Variations",
            title="Related username variants detected",
            details=f"Variations: {var_summary}",
            source="Variation enumeration",
            timestamp=timestamp,
            confidence=round_confidence(0.65),
        ))
    
    # Step 4: Cross-platform correlation analysis
    total_platform_hits = len(found_platforms) + sum(len(p) for p in variation_results.values())
    
    if len(found_platforms) >= 3:
        correlation_confidence = 0.85
        risk_level = "HIGH"
        signal = "Strong identity cluster detected across multiple platforms"
    elif len(found_platforms) == 2:
        correlation_confidence = 0.68
        risk_level = "MEDIUM"
        signal = "Moderate cross-platform correlation"
    elif len(found_platforms) == 1:
        correlation_confidence = 0.50
        risk_level = "LOW"
        signal = "Single platform presence"
    else:
        correlation_confidence = 0.25
        risk_level = "VERY_LOW"
        signal = "Minimal or no platform presence detected"
    
    result.findings.append(Finding(
        category="Cross-Platform Correlation",
        title=f"Identity clustering analysis ({risk_level})",
        details=f"{signal}. Total hits: {total_platform_hits}. Platforms: {len(found_platforms)}, Variations: {len(variation_results)}",
        source="DarkTrace X correlation engine",
        timestamp=timestamp,
        confidence=round_confidence(correlation_confidence),
    ))
    result.timeline.append(f"Correlation analysis: {risk_level} risk")
    
    # Step 5: Secondary public footprint search (supporting layer)
    result.timeline.append("Collecting secondary public footprint data")
    search_query = f'"{username}" OR "{username} profile"'
    search_encoded = search_query.replace(" ", "+")
    
    try:
        search = safe_request("https://api.allorigins.win/raw", params={"url": f"https://www.bing.com/search?q={search_encoded}"})
        if search and len(str(search)) > 100:
            result.findings.append(Finding(
                category="Public Footprint",
                title="Public web search results and mentions",
                details=f"Found public search results for '{username}' indicating online presence and potential mentions.",
                source="https://api.allorigins.win (Bing search)",
                timestamp=timestamp,
                confidence=round_confidence(0.60),
            ))
            result.timeline.append("Secondary search discovered public mentions")
        else:
            result.timeline.append("Secondary search returned limited results")
    except Exception:
        result.timeline.append("Secondary search proxy unavailable")
    
    # Step 6: Platform accessibility summary
    if blocked_platforms:
        result.findings.append(Finding(
            category="Platform Access",
            title="Platforms with access restrictions",
            details=f"The following platforms blocked or rate-limited enumeration: {', '.join(blocked_platforms)}",
            source="HTTP status detection",
            timestamp=timestamp,
            confidence=round_confidence(0.80),
        ))
    
    # Step 7: Risk scoring
    final_risk = 0.3
    
    if len(found_platforms) >= 5:
        final_risk = 0.85  # Very active account
    elif len(found_platforms) >= 3:
        final_risk = 0.70  # Active across platforms
    elif len(found_platforms) >= 2:
        final_risk = 0.55  # Moderate presence
    elif len(found_platforms) == 1:
        final_risk = 0.40  # Single platform
    else:
        final_risk = 0.25  # Minimal presence
    
    # Adjust for variations
    if len(variation_results) >= 2:
        final_risk += 0.10
    
    final_risk = min(1.0, final_risk)
    
    result.findings.append(Finding(
        category="Account Risk Score",
        title="Username exposure and reuse risk assessment",
        details=f"Risk score: {final_risk:.2f}. Factors: {len(found_platforms)} platform(s), {len(variation_results)} variation(s), public search presence.",
        source="DarkTrace X risk engine",
        timestamp=timestamp,
        confidence=round_confidence(0.80),
    ))
    result.timeline.append(f"Final risk score: {final_risk:.2f}")
    
    return result
