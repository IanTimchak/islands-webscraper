from __future__ import annotations

from scraper.models.pages import ConsentResponse


def parse_consent_response(raw_text: str, islander_id: str) -> ConsentResponse:
    """
    Parse a semicolon-delimited consent response.

    Expected shapes seen so far:
    - decline;24/377 12:31;Kenta declined to participate in your study.
    - accept;24/377 12:33;Hunter consented to be in your study.
    """
    parts = [part.strip() for part in raw_text.split(";")]

    if len(parts) < 3:
        raise ValueError(f"Unexpected consent response format: {raw_text!r}")

    outcome = parts[0]
    timestamp_text = parts[1]
    message = ";".join(parts[2:]).strip()

    return ConsentResponse(
        islander_id=islander_id,
        outcome=outcome,
        timestamp_text=timestamp_text,
        message=message,
        raw_text=raw_text,
    )