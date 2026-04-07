from __future__ import annotations

import random

from scraper.models.normalized import SampledHousehold, SamplingPlan
from scraper.models.pages import Resident, VillagePage
from scraper.services.collection import Collector


class SamplingService:
    # sampling logic for household and adult selection
    def __init__(self, collector: Collector) -> None:
        self.collector = collector

    def build_household_samples(
        self,
        village: VillagePage,
        plan: SamplingPlan,
    ) -> tuple[list[int], list[int]]:
        """
        Randomly split the village household frame into:
        - primary sampled households
        - reserve households

        Sampling is done without replacement using the recorded seed.
        """
        rng = random.Random(plan.seed)

        house_ids = list(village.house_ids)
        if not house_ids:
            raise ValueError(f"No household ids available for village {village.village_name}.")

        rng.shuffle(house_ids)

        primary_n = min(plan.households_per_village, len(house_ids))
        reserve_n = min(
            plan.reserve_households_per_village,
            max(0, len(house_ids) - primary_n),
        )

        primary_household_ids = house_ids[:primary_n]
        reserve_household_ids = house_ids[primary_n : primary_n + reserve_n]

        return primary_household_ids, reserve_household_ids

    def select_eligible_adult(
        self,
        residents: list[Resident],
        min_age: int,
        rng: random.Random,
    ) -> tuple[list[Resident], Resident | None]:
        """
        Filter residents to eligible adults and select one uniformly at random.
        """
        eligible_adults = [resident for resident in residents if resident.age >= min_age]

        if not eligible_adults:
            return eligible_adults, None

        selected_adult = rng.choice(eligible_adults)
        return eligible_adults, selected_adult

    def select_adult_from_household(
        self,
        village: VillagePage,
        house_id: int,
        min_age: int,
        seed: int,
    ) -> SampledHousehold:
        """
        Fetch a household, identify eligible adults, and select one uniformly at random.
        """
        household = self.collector.fetch_household(village=village, house_id=house_id)

        # household-specific RNG so selection stays reproducible
        rng = random.Random(f"{seed}:{village.village_id}:{house_id}")
        eligible_adults, selected_adult = self.select_eligible_adult(
            residents=household.residents,
            min_age=min_age,
            rng=rng,
        )

        if selected_adult is None:
            status = "no_eligible_adult"
        else:
            status = "selected_pending_consent"

        return SampledHousehold(
            house_id=household.house_id,
            display_house_number=getattr(household, "display_house_number", None),
            residents=household.residents,
            eligible_adults=eligible_adults,
            selected_adult=selected_adult,
            status=status,
            replacement_reason=None,
        )