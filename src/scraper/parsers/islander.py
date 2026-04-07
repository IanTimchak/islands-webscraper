from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scraper.models.pages import IslanderPage, TimelineEvent


_NAME_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_CHATID_RE = re.compile(r"var\s+chatid\s*=\s*'([^']*)'\s*;")
_AWAKE_RE = re.compile(r"var\s+awake\s*=\s*(\d+)\s*;")
_ID_RE = re.compile(r"var\s+id\s*=\s*'([^']*)'\s*;")
_AGE_RE = re.compile(r"(\d+)\s+years\s+old", re.IGNORECASE)


def _extract_script_value(pattern: re.Pattern[str], html: str, label: str) -> str:
    match = pattern.search(html)
    if not match:
        raise ValueError(f"Could not find {label} in islander page.")
    return match.group(1)


def _extract_optional_script_value(pattern: re.Pattern[str], html: str) -> str | None:
    match = pattern.search(html)
    if not match:
        return None
    return match.group(1)


def parse_islander_page(html: str) -> IslanderPage:
    """Parse an islander.php response into a structured islander page."""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    if title_tag is None:
        raise ValueError("Could not find page title in islander page.")

    name = title_tag.get_text(strip=True)
    islander_id = _extract_script_value(_ID_RE, html, "islander id")
    chatid = _extract_optional_script_value(_CHATID_RE, html)

    awake_raw = _extract_optional_script_value(_AWAKE_RE, html)
    awake = None if awake_raw is None else bool(int(awake_raw))

    summary_lines: list[str] = []
    age: int | None = None
    occupation_summary: str | None = None
    money_summary: str | None = None
    current_residence: str | None = None

    about_div = soup.find("div", id="t1")
    if about_div is None:
        raise ValueError("Could not find About tab content in islander page.")

    summary_header = about_div.find("th", string=lambda s: s and s.strip() == "Summary")
    if summary_header is None:
        raise ValueError("Could not find Summary section in islander page.")

    summary_rows = []
    row = summary_header.find_parent("tr")
    if row is None:
        raise ValueError("Could not locate Summary header row.")

    # walk rows after Summary until the next section header
    current = row.find_next_sibling("tr")
    while current is not None:
        th = current.find("th")
        if th is not None:
            break

        td = current.find("td")
        if td is not None:
            text = td.get_text(" ", strip=True)
            if text:
                summary_rows.append(text)

        current = current.find_next_sibling("tr")

    summary_lines = summary_rows

    for line in summary_lines:
        age_match = _AGE_RE.search(line)
        if age_match:
            age = int(age_match.group(1))
        elif line.startswith("$"):
            money_summary = line
        elif line.lower().startswith("lives in "):
            current_residence = line
        else:
            # if it is not age, income, or residence, first unmatched line is probably occupation
            if occupation_summary is None:
                occupation_summary = line

    timeline_events: list[TimelineEvent] = []
    current_age_stage: int | None = None

    for tr in about_div.find_all("tr"):
        th = tr.find("th")
        if th is not None:
            heading = th.get_text(" ", strip=True)
            if heading.startswith("Age "):
                try:
                    current_age_stage = int(heading.split("Age ", 1)[1])
                except ValueError:
                    current_age_stage = None
            continue

        tds = tr.find_all("td")
        if len(tds) == 2:
            date_code = tds[0].get_text(" ", strip=True)
            event_text = tds[1].get_text(" ", strip=True)
            if date_code or event_text:
                timeline_events.append(
                    TimelineEvent(
                        age_stage=current_age_stage,
                        date_code=date_code,
                        text=event_text,
                    )
                )

    return IslanderPage(
        islander_id=islander_id,
        name=name,
        chatid=chatid,
        awake=awake,
        summary_lines=summary_lines,
        age=age,
        occupation_summary=occupation_summary,
        money_summary=money_summary,
        current_residence=current_residence,
        timeline_events=timeline_events,
        raw_html=html,
    )