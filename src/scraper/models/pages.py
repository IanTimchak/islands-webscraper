from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class VillagePage:
    # human-readable village name from the page/script
    village_name: str

    # internal numeric village id from `var v = ...`
    village_id: int

    # internal island id from `var island = ...`
    island_id: int

    # list of real household ids parsed from the map array
    house_ids: list[int] = field(default_factory=list)

    # full raw HTML for debugging/re-parsing
    raw_html: str = ""


@dataclass(slots=True)
class Resident:
    # resident name shown in the house roster
    name: str

    # parsed resident age
    age: int

    # id used in islander.php?id=...
    islander_id: str


@dataclass(slots=True)
class HouseholdPage:
    # internal numeric village id
    village_id: int

    # requested internal house id used in house.php?v=...&h=...
    house_id: int

    # displayed house number from the page title, if present
    display_house_number: int | None = None

    # residents listed in the house response
    residents: list[Resident] = field(default_factory=list)

    # full raw HTML for debugging/re-parsing
    raw_html: str = ""


@dataclass(slots=True)
class IslanderPage:
    # id used in islander.php?id=...
    islander_id: str

    # displayed islander name
    name: str

    # chat session id from page script
    chatid: str | None = None

    # awake flag from page script
    awake: bool | None = None

    # full raw HTML for debugging/re-parsing
    raw_html: str = ""


@dataclass(slots=True)
class ChatResponse:
    # chat session used for the request
    chatid: str

    # question sent to alice.php
    question: str

    # extracted plain response text
    response_text: str

    # full raw response body
    raw_text: str = ""


@dataclass(slots=True)
class ConsentResponse:
    # islander id used for the consent request
    islander_id: str

    # parsed outcome like accept/reject/unknown
    outcome: str

    # human-readable consent message if available
    message: str = ""

    # full raw response text
    raw_text: str = ""