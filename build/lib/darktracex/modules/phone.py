"""Phone Number Intelligence Module for DarkTrace X.

Performs OSINT-grade phone number analysis:
- Number format validation via libphonenumber
- Geographic origin extraction
- Carrier detection
- Number type classification (mobile, landline, etc.)
- Timezone extraction
- Real metadata only (no fake location tracking, SIM owner lookups, or account linkage)
"""

from __future__ import annotations

import phonenumbers
from phonenumbers import carrier, geocoder, number_type, timezone
from datetime import datetime
from ..entities import Finding, ModuleResult
from ..utils import now_iso, round_confidence


def run_phone_intel(target: str) -> ModuleResult:
    """Run phone number intelligence investigation."""

    result = ModuleResult()
    timestamp = now_iso()
    raw = target.strip()
    result.timeline.append(
        f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
        f"Phone intelligence beginning for {raw}"
    )

    # Parse and validate phone number
    try:
        parsed = phonenumbers.parse(raw, None)
        is_valid = phonenumbers.is_valid_number(parsed)

        # Extract metadata
        country_code = parsed.country_code
        national_number = parsed.national_number
        country_name = geocoder.country_name_for_number(parsed, "en") or "Unknown"
        region_code = geocoder.region_code_for_number(parsed) or "Unknown"

        # Get carrier information (if available)
        carrier_name = carrier.name_for_number(parsed, "en") or "Not available"

        # Get number type
        num_type = number_type(parsed)
        type_str = {
            0: "Unknown",
            1: "Fixed line",
            2: "Mobile",
            3: "Fixed line or mobile",
            4: "Toll-free",
            5: "Premium rate",
            6: "Shared cost",
            7: "VoIP",
            8: "Personal number",
            9: "Pager",
            10: "UAN",
            11: "VoiceMailBox",
            12: "ISAN",
            13: "Other",
        }.get(num_type, "Unknown")

        # Get timezone
        tz_list = timezone.time_zones_for_number(parsed)
        tz_str = tz_list[0] if tz_list else "Unknown"

        # Validation finding
        result.findings.append(
            Finding(
                category="Number Validation",
                title="Phone number format and validation",
                details=f"Format: Valid={is_valid}. "
                f"Country code: +{country_code}. "
                f"National number: {national_number}.",
                source="libphonenumber",
                timestamp=timestamp,
                confidence=round_confidence(0.98 if is_valid else 0.20),
            )
        )
        result.timeline.append(
            f"Phone validation: {'VALID' if is_valid else 'INVALID'}"
        )

        # Geographic metadata
        result.findings.append(
            Finding(
                category="Geographic Origin",
                title="Country and region information",
                details=f"Country: {country_name}. Region code: {region_code}.",
                source="libphonenumber geocoder",
                timestamp=timestamp,
                confidence=round_confidence(0.85),
            )
        )
        result.timeline.append(f"Geographic origin: {country_name} / {region_code}")

        # Carrier information (if available)
        if carrier_name and carrier_name != "Not available":
            result.findings.append(
                Finding(
                    category="Carrier",
                    title="Telecommunications carrier",
                    details=f"Carrier: {carrier_name}.",
                    source="libphonenumber carrier lookup",
                    timestamp=timestamp,
                    confidence=round_confidence(0.80),
                )
            )
            result.timeline.append(f"Carrier identified: {carrier_name}")
        else:
            result.findings.append(
                Finding(
                    category="Carrier",
                    title="Carrier information unavailable",
                    details="Carrier lookup not available for this number.",
                    source="libphonenumber",
                    timestamp=timestamp,
                    confidence=round_confidence(0.60),
                )
            )
            result.timeline.append("Carrier lookup: Not available")

        # Number type
        result.findings.append(
            Finding(
                category="Number Type",
                title="Classification of number type",
                details=f"Type: {type_str}.",
                source="libphonenumber number_type",
                timestamp=timestamp,
                confidence=round_confidence(0.90),
            )
        )
        result.timeline.append(f"Number type: {type_str}")

        # Timezone
        result.findings.append(
            Finding(
                category="Timezone",
                title="Approximate timezone",
                details=f"Timezone: {tz_str}.",
                source="libphonenumber timezone lookup",
                timestamp=timestamp,
                confidence=round_confidence(0.75),
            )
        )
        result.timeline.append(f"Timezone: {tz_str}")

        # Risk assessment based on validation
        risk_score = 0.3 if is_valid else 0.8
        result.findings.append(
            Finding(
                category="Risk Scoring",
                title="Phone number validity risk score",
                details=f"Risk score: {risk_score:.2f}. "
                f"Higher score indicates invalid/suspicious format. "
                f"Based on libphonenumber validation.",
                source="DarkTrace X risk engine",
                timestamp=timestamp,
                confidence=round_confidence(0.85),
            )
        )
        result.timeline.append(f"Risk score: {risk_score:.2f}")

    except phonenumbers.NumberParseException as exc:
        result.findings.append(
            Finding(
                category="Number Validation",
                title="Phone number parsing failed",
                details=str(exc),
                source="libphonenumber",
                timestamp=timestamp,
                confidence=round_confidence(0.10),
            )
        )
        result.timeline.append("Phone parsing failed: Invalid format")
        return result

    result.timeline.append("Phone investigation complete")
    return result
