from __future__ import annotations

from dataclasses import dataclass, field

from scraper.models.pages import ChatResponse, IslanderPage, Resident, TimelineEvent


@dataclass(slots=True)
class SamplingPlan:
    # target number of completed participants for a village
    households_per_village: int

    # number of reserve households pre-generated
    reserve_households_per_village: int

    # minimum age for adult eligibility
    adults_only_min_age: int = 21

    # recorded random seed for reproducibility
    seed: int = 0

    # policy labels for bookkeeping
    village_selection_policy: str = "purposive_largest_villages"
    household_selection_policy: str = "uniform_without_replacement"
    adult_selection_policy: str = "uniform_among_eligible_adults"
    replacement_policy: str = "next_unused_reserve_household"


@dataclass(slots=True)
class SampledHousehold:
    # internal house id used in requests
    house_id: int

    # displayed house number shown by the site, if present
    display_house_number: int | None = None

    # all residents returned by the household page
    residents: list[Resident] = field(default_factory=list)

    # residents age >= minimum age
    eligible_adults: list[Resident] = field(default_factory=list)

    # chosen adult from eligible adults
    selected_adult: Resident | None = None

    # workflow status
    status: str = "unknown"

    # explanation if the household was not usable
    replacement_reason: str | None = None

    # consent results if an adult was selected
    consent_outcome: str | None = None
    consent_timestamp_text: str | None = None
    consent_message: str | None = None


@dataclass(slots=True)
class CollectedParticipant:
    village_name: str
    village_id: int
    island_id: int

    house_id: int
    display_house_number: int | None

    selected_adult: Resident

    consent_outcome: str
    consent_timestamp_text: str
    consent_message: str


@dataclass(slots=True)
class ChatQuestionSpec:
    # stable key used in output dictionaries
    key: str

    # literal text sent to the chat endpoint
    question_text: str

    # whether the question is required for the collection plan
    required: bool = True


@dataclass(slots=True)
class SummaryFieldSpec:
    # stable key used in output dictionaries
    key: str

    # attribute name to read from IslanderPage
    source: str

    # whether the field is required for the collection plan
    required: bool = False


@dataclass(slots=True)
class CollectionPlan:
    # whether to include requested summary fields
    include_summary: bool = True

    # whether to include raw timeline events
    include_timeline: bool = True

    # configurable summary fields to collect
    summary_fields: list[SummaryFieldSpec] = field(default_factory=list)

    # configurable chat questions to ask
    chat_questions: list[ChatQuestionSpec] = field(default_factory=list)


@dataclass(slots=True)
class ParticipantCollectionResult:
    # village context
    village_name: str
    village_id: int
    island_id: int

    # participant context
    islander_id: str
    islander_name: str

    # full parsed islander page for traceability
    islander: IslanderPage

    # collected summary values keyed by CollectionPlan field key
    summary_data: dict[str, object] = field(default_factory=dict)

    # collected chat responses keyed by CollectionPlan question key
    chat_data: dict[str, ChatResponse] = field(default_factory=dict)

    # optionally included raw timeline events
    timeline_events: list[TimelineEvent] = field(default_factory=list)


@dataclass(slots=True)
class VillageDataCollectionResult:
    village_name: str
    village_id: int
    island_id: int
    frame_size: int
    target_completed_participants: int

    primary_household_ids: list[int] = field(default_factory=list)
    reserve_household_ids: list[int] = field(default_factory=list)

    processed_households: list[SampledHousehold] = field(default_factory=list)

    # lightweight participant audit record
    completed_participants: list[CollectedParticipant] = field(default_factory=list)

    # full configurable collection results
    collected_participant_results: list[ParticipantCollectionResult] = field(default_factory=list)

    exhausted_reserve: bool = False


# normalization
@dataclass(slots=True)
class NormalizedParticipant:
    village_name: str
    village_id: int
    island_id: int

    islander_id: str
    islander_name: str

    age: int | None = None

    current_residence_raw: str | None = None
    current_village: str | None = None
    current_house_number: int | None = None

    money_summary_raw: str | None = None
    money_summary_value: int | None = None

    birth_village_raw: str | None = None
    birth_village: str | None = None

    income_response_raw: str | None = None
    income_numeric: int | None = None
    income_text_normalized: str | None = None

    occupation_from_income_raw: str | None = None
    occupation_summary_raw: str | None = None
    occupation_chat_raw: str | None = None
    occupation_text: str | None = None

    education_events: list[str] = field(default_factory=list)