from scraper.parsers.consent import parse_consent_response


def test_parse_consent_response_accept_full() -> None:
    raw = "accept;24/377 12:33;Hunter consented to be in your study."
    result = parse_consent_response(raw, islander_id="abc123")

    assert result.islander_id == "abc123"
    assert result.outcome == "accept"
    assert result.timestamp_text == "24/377 12:33"
    assert result.message == "Hunter consented to be in your study."


def test_parse_consent_response_decline_full() -> None:
    raw = "decline;24/377 12:31;Kenta declined to participate in your study."
    result = parse_consent_response(raw, islander_id="abc123")

    assert result.outcome == "decline"
    assert result.timestamp_text == "24/377 12:31"
    assert result.message == "Kenta declined to participate in your study."


def test_parse_consent_response_accept_short() -> None:
    raw = "accept;"
    result = parse_consent_response(raw, islander_id="abc123")

    assert result.outcome == "accept"
    assert result.timestamp_text == ""
    assert result.message == ""