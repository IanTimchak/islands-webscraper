from __future__ import annotations

from scraper.models.pages import ConsentResponse


def parse_consent_response(raw_text: str, islander_id: str) -> ConsentResponse:
    """
    Parse a semicolon-delimited consent response.

    Observed shapes:
    - decline;24/377 12:31;Kenta declined to participate in your study.
    - accept;24/377 12:33;Hunter consented to be in your study.
    - accept;
    """
    parts = [part.strip() for part in raw_text.split(";")]

    # remove trailing empty fragments caused by a final semicolon
    while parts and parts[-1] == "":
        parts.pop()

    if not parts:
        raise ValueError(f"Unexpected consent response format: {raw_text!r}")

    outcome = parts[0]
    timestamp_text = parts[1] if len(parts) >= 2 else ""
    message = ";".join(parts[2:]).strip() if len(parts) >= 3 else ""

    return ConsentResponse(
        islander_id=islander_id,
        outcome=outcome,
        timestamp_text=timestamp_text,
        message=message,
        raw_text=raw_text,
    )