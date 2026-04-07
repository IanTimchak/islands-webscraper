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

    # carry-through fields useful for downstream transforms
    current_residence_raw: str | None = None
    money_summary_raw: str | None = None
    money_summary_value: int | None = None
    income_response_raw: str | None = None
    income_numeric: int | None = None
    income_text_normalized: str | None = None
    occupation_text: str | None = None

    # analysis-facing education fields
    latest_education_event: str | None = None
    education_label: str | None = None


@dataclass(slots=True)
class SamplingRunRecord:
    run_id: str
    village_name: str
    village_id: int
    island_id: int
    frame_size: int
    target_completed_participants: int
    seed: int
    primary_household_ids: list[int] = field(default_factory=list)
    reserve_household_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ProcessedHouseholdRecord:
    run_id: str
    village_name: str
    village_id: int
    island_id: int

    house_id: int
    display_house_number: int | None = None

    resident_count: int = 0
    eligible_adult_count: int = 0

    selected_adult_id: str | None = None
    selected_adult_name: str | None = None
    selected_adult_age: int | None = None

    status: str = "unknown"
    replacement_reason: str | None = None

    consent_outcome: str | None = None
    consent_timestamp_text: str | None = None
    consent_message: str | None = None


# study-specific analysis records
@dataclass(slots=True)
class StudyRunRecord:
    run_id: str
    village_names: list[str] = field(default_factory=list)
    n_per_village: int = 0
    reserve_n_per_village: int = 0
    seed: int = 0
    summary_fields: list[str] = field(default_factory=list)
    question_keys: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VillageRunSummary:
    run_id: str
    village_name: str
    village_id: int
    island_id: int
    target_completed_participants: int
    completed_collected_participants: int
    processed_households: int
    exhausted_reserve: bool