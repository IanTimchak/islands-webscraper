from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from scraper.models.analysis import (
    ProcessedHouseholdRecord,
    SamplingRunRecord,
    StudyRunRecord,
    VillageRunSummary,
)
from scraper.models.normalized import (
    ChatQuestionSpec,
    CollectedParticipant,
    CollectionPlan,
    SamplingPlan,
    SummaryFieldSpec,
    VillageDataCollectionResult,
)
from scraper.models.pages import VillagePage
from scraper.models.runtime import StudyRunState, VillageRunState
from scraper.services.checkpoint import CheckpointService
from scraper.services.collection import Collector
from scraper.services.data_collection import DataCollectionService
from scraper.services.derivation import DerivationService
from scraper.services.normalization import NormalizationService
from scraper.services.persistence import PersistenceService
from scraper.services.progress import NullProgressReporter, ProgressReporter
from scraper.services.sampling import SamplingService


class CollectionWorkflow:
    """
    Main workflow service for long-running collection.

    Responsibilities:
    - village-level consent-aware collection
    - study-level multi-village orchestration
    - checkpoint save/load for interruption recovery
    - resume support for study runs

    Important durability rule:
    - checkpoint state is only advanced after participant-level persistence succeeds
    - this prevents resume from skipping data that was never durably written
    """

    def __init__(
        self,
        collector: Collector,
        sampling: SamplingService,
        data_collection: DataCollectionService,
        normalization: NormalizationService | None = None,
        derivation: DerivationService | None = None,
        progress: ProgressReporter | None = None,
    ) -> None:
        self.collector = collector
        self.sampling = sampling
        self.data_collection = data_collection
        self.normalization = normalization
        self.derivation = derivation
        self.progress = progress or NullProgressReporter()

    # -------------------------------------------------------------------------
    # village-level workflow
    # -------------------------------------------------------------------------

    def collect_village(
        self,
        village: VillagePage,
        sampling_plan: SamplingPlan,
        collection_plan: CollectionPlan,
    ) -> VillageDataCollectionResult:
        """
        Fresh village run with no resume state.

        This preserves the old behavior but now routes through the resumable engine.
        """
        primary_household_ids, reserve_household_ids = self.sampling.build_household_samples(
            village=village,
            plan=sampling_plan,
        )

        village_state = VillageRunState(
            village_name=village.village_name,
            village_id=village.village_id,
            island_id=village.island_id,
            primary_household_ids=list(primary_household_ids),
            reserve_household_ids=list(reserve_household_ids),
            household_queue=list(primary_household_ids),
            reserve_queue=list(reserve_household_ids),
        )

        return self._collect_village_with_state(
            village=village,
            sampling_plan=sampling_plan,
            collection_plan=collection_plan,
            village_state=village_state,
            checkpoint=None,
            study_state=None,
            village_persistence=None,
            aggregate_persistence=None,
        )

    def _collect_village_with_state(
        self,
        village: VillagePage,
        sampling_plan: SamplingPlan,
        collection_plan: CollectionPlan,
        village_state: VillageRunState,
        checkpoint: CheckpointService | None,
        study_state: StudyRunState | None,
        village_persistence: PersistenceService | None,
        aggregate_persistence: PersistenceService | None,
        aggregate_analysis_rows: list | None = None,
    ) -> VillageDataCollectionResult:
        """
        Village collection engine that can start fresh or resume from saved state.

        When `village_persistence` and `aggregate_persistence` are provided, participant
        outputs are durably written immediately after each successful participant.

        Aggregate analysis rows are optional and only used for study-level runs to track new rows across villages after resume.
        """
        result = VillageDataCollectionResult(
            village_name=village.village_name,
            village_id=village.village_id,
            island_id=village.island_id,
            frame_size=len(village.house_ids),
            target_completed_participants=sampling_plan.households_per_village,
            primary_household_ids=list(village_state.primary_household_ids),
            reserve_household_ids=list(village_state.reserve_household_ids),
        )

        reserve_queue = deque(village_state.reserve_queue)
        household_queue = deque(village_state.household_queue)

        processed_household_ids = set(village_state.processed_household_ids)
        completed_participant_ids = set(village_state.completed_participant_ids)

        processed_households = village_state.processed_household_count
        completed_count = village_state.completed_participant_count

        village_task = self.progress.start_task(
            description=(
                f"[{village.village_name}] "
                f"{completed_count}/{sampling_plan.households_per_village} participants | "
                f"processed {processed_households} households"
            ),
            total=sampling_plan.households_per_village,
            level=0,
        )

        while household_queue and completed_count < sampling_plan.households_per_village:
            house_id = household_queue.popleft()

            if house_id in processed_household_ids:
                continue

            sampled = self.sampling.select_adult_from_household(
                village=village,
                house_id=house_id,
                min_age=sampling_plan.adults_only_min_age,
                seed=sampling_plan.seed,
            )
            processed_households += 1
            result.processed_households.append(sampled)

            if sampled.selected_adult is None:
                sampled.status = "no_eligible_adult"
                sampled.replacement_reason = "no adult age 21+ in household"

                if village_persistence is not None and study_state is not None:
                    self._persist_processed_household(
                        persistence=village_persistence,
                        run_id=study_state.run_id,
                        village_result=result,
                        sampled=sampled,
                    )

                if reserve_queue:
                    replacement_house_id = reserve_queue.popleft()
                    household_queue.append(replacement_house_id)

                    if checkpoint is not None and study_state is not None:
                        checkpoint.enqueue_reserve_household(
                            state=study_state,
                            village_name=village.village_name,
                            house_id=replacement_house_id,
                        )
                else:
                    result.exhausted_reserve = True

                processed_household_ids.add(house_id)

                if checkpoint is not None and study_state is not None:
                    checkpoint.record_processed_household(
                        state=study_state,
                        village_name=village.village_name,
                        house_id=house_id,
                        exhausted_reserve=result.exhausted_reserve,
                    )

                self.progress.update_task(
                    village_task,
                    description=(
                        f"[{village.village_name}] "
                        f"{completed_count}/{sampling_plan.households_per_village} participants | "
                        f"processed {processed_households} households | house {house_id}: no eligible adult"
                    ),
                )
                continue

            islander_id = sampled.selected_adult.islander_id

            if islander_id in completed_participant_ids:
                processed_household_ids.add(house_id)

                if checkpoint is not None and study_state is not None:
                    checkpoint.record_processed_household(
                        state=study_state,
                        village_name=village.village_name,
                        house_id=house_id,
                        exhausted_reserve=result.exhausted_reserve,
                    )
                continue

            islander = self.collector.fetch_islander(
                village=village,
                islander_id=islander_id,
            )

            consent = self.collector.request_consent(islander)

            sampled.consent_outcome = consent.outcome
            sampled.consent_timestamp_text = consent.timestamp_text
            sampled.consent_message = consent.message

            if consent.outcome != "accept":
                sampled.status = "declined_consent"
                sampled.replacement_reason = "selected adult declined consent"

                if village_persistence is not None and study_state is not None:
                    self._persist_processed_household(
                        persistence=village_persistence,
                        run_id=study_state.run_id,
                        village_result=result,
                        sampled=sampled,
                    )

                if reserve_queue:
                    replacement_house_id = reserve_queue.popleft()
                    household_queue.append(replacement_house_id)

                    if checkpoint is not None and study_state is not None:
                        checkpoint.enqueue_reserve_household(
                            state=study_state,
                            village_name=village.village_name,
                            house_id=replacement_house_id,
                        )
                else:
                    result.exhausted_reserve = True

                processed_household_ids.add(house_id)

                if checkpoint is not None and study_state is not None:
                    checkpoint.record_processed_household(
                        state=study_state,
                        village_name=village.village_name,
                        house_id=house_id,
                        exhausted_reserve=result.exhausted_reserve,
                    )

                self.progress.update_task(
                    village_task,
                    description=(
                        f"[{village.village_name}] "
                        f"{completed_count}/{sampling_plan.households_per_village} participants | "
                        f"processed {processed_households} households | house {house_id}: consent declined"
                    ),
                )
                continue

            sampled.status = "consented"

            completed_participant = CollectedParticipant(
                village_name=village.village_name,
                village_id=village.village_id,
                island_id=village.island_id,
                house_id=sampled.house_id,
                display_house_number=sampled.display_house_number,
                selected_adult=sampled.selected_adult,
                consent_outcome=consent.outcome,
                consent_timestamp_text=consent.timestamp_text,
                consent_message=consent.message,
            )

            participant_result = self.data_collection.collect_participant(
                village=village,
                islander_id=islander_id,
                plan=collection_plan,
            )

            result.completed_participants.append(completed_participant)
            result.collected_participant_results.append(participant_result)

            if village_persistence is not None and study_state is not None:
                self._persist_processed_household(
                    persistence=village_persistence,
                    run_id=study_state.run_id,
                    village_result=result,
                    sampled=sampled,
                )

            if (
                village_persistence is not None
                and aggregate_persistence is not None
                and self.normalization is not None
                and self.derivation is not None
            ):
                village_persistence.persist_participant_collection(participant_result)

                normalized = self.normalization.normalize_participant(participant_result)
                village_persistence.persist_normalized_participant(normalized)

                analysis_row = self.derivation.derive_analysis_row(normalized)
                village_persistence.append_analysis_row_jsonl(analysis_row)

                aggregate_persistence.append_analysis_row_jsonl(analysis_row)

                if aggregate_analysis_rows is not None:
                    aggregate_analysis_rows.append(analysis_row)

            completed_count += 1
            processed_household_ids.add(house_id)
            completed_participant_ids.add(islander_id)

            if checkpoint is not None and study_state is not None:
                checkpoint.record_processed_household(
                    state=study_state,
                    village_name=village.village_name,
                    house_id=house_id,
                    exhausted_reserve=result.exhausted_reserve,
                )
                checkpoint.record_completed_participant(
                    state=study_state,
                    village_name=village.village_name,
                    islander_id=islander_id,
                )

            self.progress.update_task(
                village_task,
                advance=1,
                description=(
                    f"[{village.village_name}] "
                    f"{completed_count}/{sampling_plan.households_per_village} participants | "
                    f"processed {processed_households} households"
                ),
            )

        if completed_count < sampling_plan.households_per_village and not household_queue and not reserve_queue:
            result.exhausted_reserve = True

        final_description = (
            f"[{village.village_name}] "
            f"{completed_count}/{sampling_plan.households_per_village} participants | "
            f"processed {processed_households} households"
        )
        if result.exhausted_reserve:
            final_description += " | reserve exhausted"

        self.progress.finish_task(village_task, description=final_description)

        village_state.household_queue = list(household_queue)
        village_state.reserve_queue = list(reserve_queue)
        village_state.processed_household_ids = list(processed_household_ids)
        village_state.completed_participant_ids = list(completed_participant_ids)
        village_state.processed_household_count = processed_households
        village_state.completed_participant_count = completed_count
        village_state.exhausted_reserve = result.exhausted_reserve
        village_state.is_complete = completed_count >= sampling_plan.households_per_village

        return result

    # -------------------------------------------------------------------------
    # study-level workflow
    # -------------------------------------------------------------------------

    def collect_study(
        self,
        village_names: list[str],
        sampling_plan: SamplingPlan,
        collection_plan: CollectionPlan,
        persistence: PersistenceService,
        question_specs: list[str],
    ) -> list:
        checkpoint = CheckpointService(persistence.output_dir)

        state = checkpoint.initialize(
            run_id=persistence.run_id,
            seed=sampling_plan.seed,
            n_per_village=sampling_plan.households_per_village,
            reserve_n_per_village=sampling_plan.reserve_households_per_village,
            min_age=sampling_plan.adults_only_min_age,
            include_timeline=collection_plan.include_timeline,
            summary_fields=[field.source for field in collection_plan.summary_fields],
            question_specs=question_specs,
            village_names=village_names,
        )

        try:
            return self._run_study_from_state(
                state=state,
                checkpoint=checkpoint,
                persistence=persistence,
                sampling_plan=sampling_plan,
                collection_plan=collection_plan,
            )
        except BaseException:
            checkpoint.mark_interrupted(state)
            raise

    def resume_study(
        self,
        persistence: PersistenceService,
    ) -> list:
        checkpoint = CheckpointService(persistence.output_dir)
        state = checkpoint.load()

        summary_fields = list(state.summary_fields)
        question_specs = list(state.question_specs)

        collection_plan = CollectionPlan(
            include_summary=True,
            include_timeline=state.include_timeline,
            summary_fields=[
                SummaryFieldSpec(key=field_name, source=field_name, required=False)
                for field_name in summary_fields
            ],
            chat_questions=[
                self._parse_question_spec(raw_question)
                for raw_question in question_specs
            ],
        )

        sampling_plan = SamplingPlan(
            households_per_village=state.n_per_village,
            reserve_households_per_village=state.reserve_n_per_village,
            adults_only_min_age=state.min_age,
            seed=state.seed,
        )

        try:
            return self._run_study_from_state(
                state=state,
                checkpoint=checkpoint,
                persistence=persistence,
                sampling_plan=sampling_plan,
                collection_plan=collection_plan,
            )
        except BaseException:
            checkpoint.mark_interrupted(state)
            raise

    def _run_study_from_state(
        self,
        state: StudyRunState,
        checkpoint: CheckpointService,
        persistence: PersistenceService,
        sampling_plan: SamplingPlan,
        collection_plan: CollectionPlan,
    ) -> list:
        if self.normalization is None:
            raise RuntimeError("CollectionWorkflow requires NormalizationService for study runs.")
        if self.derivation is None:
            raise RuntimeError("CollectionWorkflow requires DerivationService for study runs.")

        new_analysis_rows: list = []

        persistence.append_jsonl_record(
            persistence.raw_dir / "study_run.jsonl",
            StudyRunRecord(
                run_id=state.run_id,
                village_names=state.village_names,
                n_per_village=state.n_per_village,
                reserve_n_per_village=state.reserve_n_per_village,
                seed=state.seed,
                summary_fields=state.summary_fields,
                question_keys=[self._parse_question_spec(q).key for q in state.question_specs],
            ),
        )

        for village_name in state.village_names:
            village_state = state.villages[village_name]

            if village_state.is_complete:
                continue

            village = self.collector.fetch_village(village_name)

            if not village_state.primary_household_ids:
                primary_household_ids, reserve_household_ids = self.sampling.build_household_samples(
                    village=village,
                    plan=sampling_plan,
                )

                checkpoint.mark_village_initialized(
                    state=state,
                    village_name=village_name,
                    village_id=village.village_id,
                    island_id=village.island_id,
                    primary_household_ids=primary_household_ids,
                    reserve_household_ids=reserve_household_ids,
                )

            village_run_id = f"village-{self._slugify(village_name)}"
            village_persistence = PersistenceService(
                data_dir=persistence.data_dir,
                run_id=village_run_id,
                save_debug_payloads=persistence.save_debug_payloads,
                base_dir=persistence.output_dir / "villages",
            )

            village_persistence.persist_sampling_run(
                SamplingRunRecord(
                    run_id=state.run_id,
                    village_name=village.village_name,
                    village_id=village.village_id,
                    island_id=village.island_id,
                    frame_size=len(village.house_ids),
                    target_completed_participants=sampling_plan.households_per_village,
                    seed=sampling_plan.seed,
                    primary_household_ids=village_state.primary_household_ids,
                    reserve_household_ids=village_state.reserve_household_ids,
                )
            )

            village_result = self._collect_village_with_state(
                village=village,
                sampling_plan=sampling_plan,
                collection_plan=collection_plan,
                village_state=village_state,
                checkpoint=checkpoint,
                study_state=state,
                village_persistence=village_persistence,
                aggregate_persistence=persistence,
                aggregate_analysis_rows=None,
            )

            village_summary = VillageRunSummary(
                run_id=state.run_id,
                village_name=village_result.village_name,
                village_id=village_result.village_id,
                island_id=village_result.island_id,
                target_completed_participants=village_result.target_completed_participants,
                completed_collected_participants=village_state.completed_participant_count,
                processed_households=village_state.processed_household_count,
                exhausted_reserve=village_result.exhausted_reserve,
            )
            persistence.append_jsonl_record(
                persistence.raw_dir / "village_summaries.jsonl",
                village_summary,
            )

            # rebuild village CSV from its full JSONL source of truth
            self._rebuild_analysis_csv_from_jsonl(village_persistence)

            # track only rows written in this pass for summary output
            village_new_rows = self._load_analysis_rows_jsonl(village_persistence)
            new_analysis_rows.extend(village_new_rows)

            checkpoint.mark_village_complete(
                state=state,
                village_name=village_name,
                exhausted_reserve=village_result.exhausted_reserve,
            )

        # rebuild study CSV from the full study-level JSONL source of truth
        self._rebuild_analysis_csv_from_jsonl(persistence)
        checkpoint.mark_complete(state)

        return new_analysis_rows

    # -------------------------------------------------------------------------
    # small helpers
    # -------------------------------------------------------------------------

    def _parse_question_spec(self, raw_question: str) -> ChatQuestionSpec:
        if "=" not in raw_question:
            raise ValueError(
                f"Question spec must look like key=Question text, got: {raw_question!r}"
            )

        key, question_text = raw_question.split("=", 1)
        key = key.strip()
        question_text = question_text.strip()

        if not key or not question_text:
            raise ValueError(
                f"Question spec must include both key and question text, got: {raw_question!r}"
            )

        return ChatQuestionSpec(
            key=key,
            question_text=question_text,
            required=False,
        )

    def _slugify(self, value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.strip())

    def _persist_processed_household(
        self,
        persistence: PersistenceService,
        run_id: str,
        village_result: VillageDataCollectionResult,
        sampled,
    ) -> None:
        persistence.persist_processed_household(
            ProcessedHouseholdRecord(
                run_id=run_id,
                village_name=village_result.village_name,
                village_id=village_result.village_id,
                island_id=village_result.island_id,
                house_id=sampled.house_id,
                display_house_number=sampled.display_house_number,
                resident_count=len(sampled.residents),
                eligible_adult_count=len(sampled.eligible_adults),
                selected_adult_id=(
                    sampled.selected_adult.islander_id if sampled.selected_adult else None
                ),
                selected_adult_name=(
                    sampled.selected_adult.name if sampled.selected_adult else None
                ),
                selected_adult_age=(
                    sampled.selected_adult.age if sampled.selected_adult else None
                ),
                status=sampled.status,
                replacement_reason=sampled.replacement_reason,
                consent_outcome=sampled.consent_outcome,
                consent_timestamp_text=sampled.consent_timestamp_text,
                consent_message=sampled.consent_message,
            )
        )

    def _analysis_jsonl_path(self, persistence: PersistenceService) -> Path:
        return Path(persistence.analysis_dir) / "analysis_rows.jsonl"

    def _load_analysis_rows_jsonl(self, persistence: PersistenceService) -> list[dict]:
        path = self._analysis_jsonl_path(persistence)
        if not path.exists():
            return []

        rows: list[dict] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    def _rebuild_analysis_csv_from_jsonl(self, persistence: PersistenceService) -> None:
        rows = self._load_analysis_rows_jsonl(persistence)
        if not rows:
            return
        persistence.write_analysis_rows_csv(rows)