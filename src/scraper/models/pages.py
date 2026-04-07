from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TimelineEvent:
    # age header this event belongs under, e.g. 18
    age_stage: int | None

    # left-column date code, e.g. 08/372
    date_code: str

    # right-column event text
    text: str


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

    # raw summary lines from the top summary table
    summary_lines: list[str] = field(default_factory=list)

    # parsed age if present
    age: int | None = None

    # parsed summary occupation if present
    occupation_summary: str | None = None

    # parsed summary money if present
    money_summary: str | None = None

    # parsed current residence line if present
    current_residence: str | None = None

    # raw timeline events
    timeline_events: list[TimelineEvent] = field(default_factory=list)

    # full raw HTML for debugging/re-parsing
    raw_html: str = ""


@dataclass(slots=True)
class ChatResponse:
    # chat session used for the request
    chatid: str

    # exact question sent
    question: str

    # extracted chatbot-visible response text
    response_text: str

    # any key=value updates returned by the backend
    state_updates: dict[str, str] = field(default_factory=dict)

    # raw response split into lines for debugging
    raw_lines: list[str] = field(default_factory=list)

    # full raw response body
    raw_text: str = ""


"""
The simulator appears to allow direct chat requests without a prior successful study-consent request in some cases. 
However, for data collection workflows intended for the project dataset, the tool will treat consent as required 
for inclusion and will not continue official subject collection after a declined consent response.
"""
@dataclass(slots=True)
class ConsentResponse:
    # islander id used for the consent request
    islander_id: str

    # parsed outcome, e.g. accept / decline
    outcome: str

    # timestamp text returned by the endpoint
    timestamp_text: str = ""

    # human-readable consent message
    message: str = ""

    # full raw response text
    raw_text: str = ""