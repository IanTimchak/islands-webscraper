import pytest

from scraper.parsers.chat import parse_chat_response


def test_parse_chat_response_text_only() -> None:
    raw = "I was born in Shinobi."
    result = parse_chat_response(
        raw_text=raw,
        chatid="chat123",
        question="Which village were you born in?",
    )

    assert result.chatid == "chat123"
    assert result.question == "Which village were you born in?"
    assert result.response_text == "I was born in Shinobi."
    assert result.state_updates == {}


def test_parse_chat_response_with_state_updates() -> None:
    raw = "mood=happy\nI earn around $29 a day as a waiter."
    result = parse_chat_response(
        raw_text=raw,
        chatid="chat123",
        question="What is your income?",
    )

    assert result.state_updates == {"mood": "happy"}
    assert "I earn around $29 a day as a waiter." in result.response_text


def test_parse_chat_response_login_guard() -> None:
    with pytest.raises(ValueError, match="login is required"):
        parse_chat_response(
            raw_text="login\n",
            chatid="chat123",
            question="What is your income?",
        )