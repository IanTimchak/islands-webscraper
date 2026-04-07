from __future__ import annotations

from collections import deque

from scraper.models.normalized import (
    CollectedParticipant,
    CollectionPlan,
    SamplingPlan,
    VillageDataCollectionResult,
)
from scraper.models.pages import VillagePage
from scraper.services.collection import Collector
from scraper.services.data_collection import DataCollectionService
from scraper.services.progress import NullProgressReporter, ProgressReporter
from scraper.services.sampling import SamplingService


class CollectionWorkflow:
    """
    Consent-aware village collection workflow.

    This slice does:
    - randomized primary + reserve household selection
    - eligible adult selection
    - consent requests
    - configurable participant data collection
    - reserve replacement on failure
    - stop when target completed participants is reached
    """

    def __init__(
        self,
        collector: Collector,
        sampling: SamplingService,
        data_collection: DataCollectionService,
        progress: ProgressReporter | None = None,
    ) -> None:
        self.collector = collector
        self.sampling = sampling
        self.data_collection = data_collection
        self.progress = progress or NullProgressReporter()

    def collect_village(
        self,
        village: VillagePage,
        sampling_plan: SamplingPlan,
        collection_plan: CollectionPlan,
    ) -> VillageDataCollectionResult:
        primary_household_ids, reserve_household_ids = self.sampling.build_household_samples(
            village=village,
            plan=sampling_plan,
        )

        result = VillageDataCollectionResult(
            village_name=village.village_name,
            village_id=village.village_id,
            island_id=village.island_id,
            frame_size=len(village.house_ids),
            target_completed_participants=sampling_plan.households_per_village,
            primary_household_ids=primary_household_ids,
            reserve_household_ids=reserve_household_ids,
        )

        reserve_queue = deque(reserve_household_ids)
        household_queue = deque(primary_household_ids)

        processed_households = 0

        village_task = self.progress.start_task(
            description=(
                f"[{village.village_name}] 0/{sampling_plan.households_per_village} "
                f"participants | processed 0 households"
            ),
            total=sampling_plan.households_per_village,
            level=0,
        )

        while (
            household_queue
            and len(result.collected_participant_results) < sampling_plan.households_per_village
        ):
            house_id = household_queue.popleft()
            processed_households += 1

            sampled = self.sampling.select_adult_from_household(
                village=village,
                house_id=house_id,
                min_age=sampling_plan.adults_only_min_age,
                seed=sampling_plan.seed,
            )

            result.processed_households.append(sampled)

            if sampled.selected_adult is None:
                sampled.status = "no_eligible_adult"
                sampled.replacement_reason = "no adult age 21+ in household"

                self.progress.update_task(
                    village_task,
                    description=(
                        f"[{village.village_name}] "
                        f"{len(result.collected_participant_results)}/{sampling_plan.households_per_village} "
                        f"participants | processed {processed_households} households | "
                        f"house {sampled.house_id}: no eligible adult"
                    ),
                )

                if reserve_queue:
                    replacement_house_id = reserve_queue.popleft()
                    household_queue.append(replacement_house_id)
                else:
                    result.exhausted_reserve = True

                continue

            islander = self.collector.fetch_islander(
                village=village,
                islander_id=sampled.selected_adult.islander_id,
            )

            consent = self.collector.request_consent(islander)

            sampled.consent_outcome = consent.outcome
            sampled.consent_timestamp_text = consent.timestamp_text
            sampled.consent_message = consent.message

            if consent.outcome != "accept":
                sampled.status = "declined_consent"
                sampled.replacement_reason = "selected adult declined consent"

                self.progress.update_task(
                    village_task,
                    description=(
                        f"[{village.village_name}] "
                        f"{len(result.collected_participant_results)}/{sampling_plan.households_per_village} "
                        f"participants | processed {processed_households} households | "
                        f"house {sampled.house_id}: consent declined"
                    ),
                )

                if reserve_queue:
                    replacement_house_id = reserve_queue.popleft()
                    household_queue.append(replacement_house_id)
                else:
                    result.exhausted_reserve = True

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
                islander_id=sampled.selected_adult.islander_id,
                plan=collection_plan,
            )

            result.completed_participants.append(completed_participant)
            result.collected_participant_results.append(participant_result)

            self.progress.update_task(
                village_task,
                advance=1,
                description=(
                    f"[{village.village_name}] "
                    f"{len(result.collected_participant_results)}/{sampling_plan.households_per_village} "
                    f"participants | processed {processed_households} households"
                ),
            )

        if (
            len(result.collected_participant_results) < sampling_plan.households_per_village
            and not household_queue
            and not reserve_queue
        ):
            result.exhausted_reserve = True

        final_description = (
            f"[{village.village_name}] "
            f"{len(result.collected_participant_results)}/{sampling_plan.households_per_village} "
            f"participants | processed {processed_households} households"
        )
        if result.exhausted_reserve:
            final_description += " | reserve exhausted"

        self.progress.finish_task(village_task, description=final_description)
        return result