from __future__ import annotations

from scraper.models.pages import ChatResponse


def parse_chat_response(raw_text: str, chatid: str, question: str) -> ChatResponse:
    """
    Parse the raw alice.php response into response text and state updates.

    The site JS treats:
    - lines starting with "<" as response content
    - lines shaped like key=value as state updates
    - everything else as response content
    """
    lines = raw_text.splitlines()

    # guard against expired auth behavior observed in the site JS
    if lines and lines[0].strip() == "login":
        raise ValueError("Chat response indicates login is required.")

    response_parts: list[str] = []
    state_updates: dict[str, str] = {}

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("<"):
            response_parts.append(stripped)
            continue

        bits = stripped.split("=", 1)
        if len(bits) == 2 and bits[0]:
            state_updates[bits[0]] = bits[1]
            continue

        response_parts.append(stripped)

    response_text = "\n".join(response_parts).strip()

    return ChatResponse(
        chatid=chatid,
        question=question,
        response_text=response_text,
        state_updates=state_updates,
        raw_lines=lines,
        raw_text=raw_text,
    )