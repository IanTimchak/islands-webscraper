from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from scraper.models.runtime import StudyRunState, VillageRunState


class CheckpointService:
    """
    Saves and loads checkpoint state for resumable study runs.

    Recommended location:
        data/runs/<run_id>/state/run_state.json
    """

    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)
        self.state_dir = self.run_dir / "state"
        self.state_path = self.state_dir / "run_state.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def initialize(
        self,
        *,
        run_id: str,
        seed: int,
        n_per_village: int,
        reserve_n_per_village: int,
        min_age: int,
        include_timeline: bool,
        summary_fields: list[str],
        question_specs: list[str],
        village_names: list[str],
    ) -> StudyRunState:
        state = StudyRunState(
            run_id=run_id,
            seed=seed,
            n_per_village=n_per_village,
            reserve_n_per_village=reserve_n_per_village,
            min_age=min_age,
            include_timeline=include_timeline,
            summary_fields=list(summary_fields),
            question_specs=list(question_specs),
            village_names=list(village_names),
            villages={name: VillageRunState(village_name=name) for name in village_names},
            status="running",
        )
        self.save(state)
        return state

    def save(self, state: StudyRunState) -> None:
        payload = asdict(state)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self) -> StudyRunState:
        if not self.state_path.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {self.state_path}")

        payload = json.loads(self.state_path.read_text(encoding="utf-8"))

        villages = {
            name: VillageRunState(**village_payload)
            for name, village_payload in payload.get("villages", {}).items()
        }

        return StudyRunState(
            run_id=payload["run_id"],
            seed=payload["seed"],
            n_per_village=payload["n_per_village"],
            reserve_n_per_village=payload["reserve_n_per_village"],
            min_age=payload["min_age"],
            include_timeline=payload["include_timeline"],
            summary_fields=list(payload.get("summary_fields", [])),
            question_specs=list(payload.get("question_specs", [])),
            village_names=list(payload.get("village_names", [])),
            villages=villages,
            status=payload.get("status", "running"),
        )

    def mark_interrupted(self, state: StudyRunState) -> None:
        state.status = "interrupted"
        self.save(state)

    def mark_complete(self, state: StudyRunState) -> None:
        state.status = "complete"
        self.save(state)

    def mark_village_initialized(
        self,
        state: StudyRunState,
        *,
        village_name: str,
        village_id: int,
        island_id: int,
        primary_household_ids: list[int],
        reserve_household_ids: list[int],
    ) -> None:
        village_state = state.villages[village_name]
        village_state.village_id = village_id
        village_state.island_id = island_id
        village_state.primary_household_ids = list(primary_household_ids)
        village_state.reserve_household_ids = list(reserve_household_ids)
        village_state.household_queue = list(primary_household_ids)
        village_state.reserve_queue = list(reserve_household_ids)
        self.save(state)

    def record_processed_household(
        self,
        state: StudyRunState,
        *,
        village_name: str,
        house_id: int,
        exhausted_reserve: bool,
    ) -> None:
        village_state = state.villages[village_name]

        if village_state.household_queue and village_state.household_queue[0] == house_id:
            village_state.household_queue.pop(0)
        elif house_id in village_state.household_queue:
            village_state.household_queue.remove(house_id)

        if house_id not in village_state.processed_household_ids:
            village_state.processed_household_ids.append(house_id)

        village_state.processed_household_count += 1
        village_state.exhausted_reserve = exhausted_reserve
        self.save(state)

    def enqueue_reserve_household(
        self,
        state: StudyRunState,
        *,
        village_name: str,
        house_id: int,
    ) -> None:
        village_state = state.villages[village_name]

        if village_state.reserve_queue and village_state.reserve_queue[0] == house_id:
            village_state.reserve_queue.pop(0)
        elif house_id in village_state.reserve_queue:
            village_state.reserve_queue.remove(house_id)

        village_state.household_queue.append(house_id)
        self.save(state)

    def record_completed_participant(
        self,
        state: StudyRunState,
        *,
        village_name: str,
        islander_id: str,
    ) -> None:
        village_state = state.villages[village_name]

        if islander_id not in village_state.completed_participant_ids:
            village_state.completed_participant_ids.append(islander_id)

        village_state.completed_participant_count += 1
        self.save(state)

    def mark_village_complete(
        self,
        state: StudyRunState,
        *,
        village_name: str,
        exhausted_reserve: bool,
    ) -> None:
        village_state = state.villages[village_name]
        village_state.is_complete = True
        village_state.exhausted_reserve = exhausted_reserve
        self.save(state)
