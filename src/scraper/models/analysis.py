from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AnalysisRow:
    # core identifiers
    village_name: str
    village_id: int
    island_id: int
    islander_id: str
    islander_name: str

    # normalized carry-through values
    age: int | None = None
    current_village: str | None = None
    current_island_id: int | None = None
    birth_village: str | None = None
    birth_island_id: int | None = None
    immigrant_other_island: bool | None = None

    # carry-through fields that are useful for downstream transforms
    current_residence_raw: str | None = None
    money_summary_raw: str | None = None
    money_summary_value: int | None = None
    income_response_raw: str | None = None
    income_numeric: int | None = None
    income_text_normalized: str | None = None
    occupation_text: str | None = None
    education_events: list[str] = field(default_factory=list)