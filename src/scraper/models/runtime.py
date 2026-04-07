from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class VillageRunState:
    """
    Resume/checkpoint state for a single village inside a study run.
    """

    village_name: str
    village_id: int | None = None
    island_id: int | None = None

    primary_household_ids: list[int] = field(default_factory=list)
    reserve_household_ids: list[int] = field(default_factory=list)

    household_queue: list[int] = field(default_factory=list)
    reserve_queue: list[int] = field(default_factory=list)

    processed_household_ids: list[int] = field(default_factory=list)
    completed_participant_ids: list[str] = field(default_factory=list)

    processed_household_count: int = 0
    completed_participant_count: int = 0

    exhausted_reserve: bool = False
    is_complete: bool = False


@dataclass(slots=True)
class StudyRunState:
    """
    Resume/checkpoint state for a multi-village study run.

    `summary_fields` stores the collection-plan summary-field sources.
    `question_specs` stores the original CLI-style key=question text strings.
    """

    run_id: str
    seed: int
    n_per_village: int
    reserve_n_per_village: int
    min_age: int
    include_timeline: bool

    summary_fields: list[str] = field(default_factory=list)
    question_specs: list[str] = field(default_factory=list)

    village_names: list[str] = field(default_factory=list)
    villages: dict[str, VillageRunState] = field(default_factory=dict)

    status: str = "running"  # running / interrupted / complete
