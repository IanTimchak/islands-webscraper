from __future__ import annotations

import re

from bs4 import BeautifulSoup

from scraper.models.pages import HouseholdPage, Resident


_HOUSE_TITLE_RE = re.compile(r"House\s+(\d+)")


def parse_household_page(
    html: str,
    village_id: int,
    requested_house_id: int,
) -> HouseholdPage:
    """Parse a house.php response into a structured household page."""
    soup = BeautifulSoup(html, "html.parser")

    house_title = soup.find("h4", class_="house")
    if house_title is None:
        raise ValueError("Could not find house title in household page.")

    title_text = house_title.get_text(strip=True)
    title_match = _HOUSE_TITLE_RE.search(title_text)

    display_house_number: int | None = None
    if title_match:
        display_house_number = int(title_match.group(1))

    residents_table = soup.find("table", class_="residents")
    if residents_table is None:
        raise ValueError("Could not find residents table in household page.")

    residents: list[Resident] = []

    for row in residents_table.find_all("tr"):
        resident_td = row.find("td", class_="resident")
        age_td = row.find("td", class_="age")

        if resident_td is None or age_td is None:
            continue

        link = resident_td.find("a")
        if link is None:
            continue

        name = link.get_text(strip=True)
        href = link.get("href", "")

        if "islander.php?id=" not in href:
            continue

        islander_id = href.split("islander.php?id=", 1)[1].strip()
        age_text = age_td.get_text(strip=True)

        try:
            age = int(age_text)
        except ValueError as exc:
            raise ValueError(
                f"Could not parse resident age {age_text!r} for resident {name!r}."
            ) from exc

        residents.append(
            Resident(
                name=name,
                age=age,
                islander_id=islander_id,
            )
        )

    return HouseholdPage(
        village_id=village_id,
        house_id=requested_house_id,
        display_house_number=display_house_number,
        residents=residents,
        raw_html=html,
    )