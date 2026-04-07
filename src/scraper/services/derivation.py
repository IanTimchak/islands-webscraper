from __future__ import annotations

from scraper.models.analysis import AnalysisRow
from scraper.models.normalized import NormalizedParticipant


class DerivationService:
    """
    Minimal derivation layer for deterministic study variables.

    This service intentionally does only:
    - village -> island lookup
    - current island derivation
    - birth island derivation
    - immigrant status derivation
    - compact education categorization for analysis output

    Subjective recodes like occupation grouping are left for downstream transforms.
    """

    def __init__(self, village_to_island: dict[str, int]) -> None:
        self.village_to_island = village_to_island

    def derive_analysis_row(
        self,
        normalized: NormalizedParticipant,
    ) -> AnalysisRow:
        current_island_id = self._map_village_to_island(normalized.current_village)
        birth_island_id = self._map_village_to_island(normalized.birth_village)
        immigrant_other_island = self._derive_immigrant_other_island(
            current_island_id=current_island_id,
            birth_island_id=birth_island_id,
        )

        latest_education_event, education_label = self._derive_education(
            normalized.education_events
        )

        return AnalysisRow(
            village_name=normalized.village_name,
            village_id=normalized.village_id,
            island_id=normalized.island_id,
            islander_id=normalized.islander_id,
            islander_name=normalized.islander_name,
            age=normalized.age,
            current_village=normalized.current_village,
            current_island_id=current_island_id,
            birth_village=normalized.birth_village,
            birth_island_id=birth_island_id,
            immigrant_other_island=immigrant_other_island,
            current_residence_raw=normalized.current_residence_raw,
            money_summary_raw=normalized.money_summary_raw,
            money_summary_value=normalized.money_summary_value,
            income_response_raw=normalized.income_response_raw,
            income_numeric=normalized.income_numeric,
            income_text_normalized=normalized.income_text_normalized,
            occupation_text=normalized.occupation_text,
            latest_education_event=latest_education_event,
            education_label=education_label,
        )

    def _map_village_to_island(self, village_name: str | None) -> int | None:
        if not village_name:
            return None
        return self.village_to_island.get(village_name)

    def _derive_immigrant_other_island(
        self,
        current_island_id: int | None,
        birth_island_id: int | None,
    ) -> bool | None:
        if current_island_id is None or birth_island_id is None:
            return None
        return current_island_id != birth_island_id

    def _derive_education(
        self,
        education_events: list[str],
    ) -> tuple[str | None, str | None]:
        if not education_events:
            return None, "no_graduation_event"

        latest_event = education_events[-1].strip()
        lowered = latest_event.lower()

        if "university" in lowered:
            return latest_event, "university"

        if "high school" in lowered:
            return latest_event, "high_school"

        if "elementary" in lowered:
            return latest_event, "elementary"

        return latest_event, "graduated_other"