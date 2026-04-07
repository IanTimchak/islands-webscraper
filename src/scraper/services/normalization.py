from __future__ import annotations

import re

from scraper.models.normalized import NormalizedParticipant, ParticipantCollectionResult


_CURRENT_RESIDENCE_RE = re.compile(r"^Lives in\s+(.+?)\s+(\d+)$", re.IGNORECASE)
_MONEY_RE = re.compile(r"\$([\d,]+)")
_BORN_IN_RE = re.compile(
    r"\b(?:born in|I was born in)\s+([A-Za-zÀ-ÿ' -]+?)(?:[.!]|$)",
    re.IGNORECASE,
)
_INCOME_NUMERIC_RE = re.compile(r"\$([\d,]+)")
_OCCUPATION_FROM_INCOME_RE = re.compile(
    r"\bas a[n]?\s+([A-Za-zÀ-ÿ' -]+?)(?:[.!]|$)",
    re.IGNORECASE,
)
_GRADUATED_RE = re.compile(r"\bGraduated\b", re.IGNORECASE)


class NormalizationService:
    """
    Generic normalization layer.

    This service parses structured facts from collected participant results.
    It does not yet derive project-specific analytical variables like:
    - immigrant_other_island
    - occupation_group
    - education_level
    """

    def normalize_participant(
        self,
        collected: ParticipantCollectionResult,
    ) -> NormalizedParticipant:
        age = self._coerce_int(collected.summary_data.get("age"))

        current_residence_raw = self._coerce_str(
            collected.summary_data.get("current_residence")
        )
        current_village, current_house_number = self._parse_current_residence(
            current_residence_raw
        )

        money_summary_raw = self._coerce_str(
            collected.summary_data.get("money_summary")
        )
        money_summary_value = self._parse_money_value(money_summary_raw)

        birth_village_raw = None
        birth_village = None
        if "birth_village" in collected.chat_data:
            birth_village_raw = collected.chat_data["birth_village"].response_text
            birth_village = self._parse_birth_village(birth_village_raw)

        income_response_raw = None
        income_numeric = None
        income_text_normalized = None
        if "income" in collected.chat_data:
            income_response_raw = collected.chat_data["income"].response_text
            income_numeric, income_text_normalized = self._parse_income_response(
                income_response_raw
            )

        occupation_summary_raw = self._coerce_str(
            collected.summary_data.get("occupation_summary")
        )

        occupation_chat_raw = None
        if "occupation" in collected.chat_data:
            occupation_chat_raw = collected.chat_data["occupation"].response_text

        occupation_from_income_raw = self._parse_occupation_from_income_response(
            income_response_raw
        )

        occupation_text = self._choose_occupation_text(
            occupation_summary_raw,
            occupation_chat_raw,
            occupation_from_income_raw,
        )

        education_events = self._extract_education_events(collected)

        return NormalizedParticipant(
            village_name=collected.village_name,
            village_id=collected.village_id,
            island_id=collected.island_id,
            islander_id=collected.islander_id,
            islander_name=collected.islander_name,
            age=age,
            current_residence_raw=current_residence_raw,
            current_village=current_village,
            current_house_number=current_house_number,
            money_summary_raw=money_summary_raw,
            money_summary_value=money_summary_value,
            birth_village_raw=birth_village_raw,
            birth_village=birth_village,
            income_response_raw=income_response_raw,
            income_numeric=income_numeric,
            income_text_normalized=income_text_normalized,
            occupation_summary_raw=occupation_summary_raw,
            occupation_chat_raw=occupation_chat_raw,
            occupation_from_income_raw=occupation_from_income_raw,
            occupation_text=occupation_text,
            education_events=education_events,
        )

    def _coerce_str(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    def _coerce_int(self, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            return int(str(value).strip())
        except ValueError:
            return None

    def _parse_current_residence(self, text: str | None) -> tuple[str | None, int | None]:
        if not text:
            return None, None

        match = _CURRENT_RESIDENCE_RE.search(text)
        if not match:
            return None, None

        village = match.group(1).strip()
        house_number = int(match.group(2))
        return village, house_number

    def _parse_money_value(self, text: str | None) -> int | None:
        if not text:
            return None

        match = _MONEY_RE.search(text)
        if not match:
            return None

        return int(match.group(1).replace(",", ""))

    def _parse_birth_village(self, text: str | None) -> str | None:
        if not text:
            return None

        match = _BORN_IN_RE.search(text)
        if not match:
            return None

        return match.group(1).strip()

    def _parse_income_response(self, text: str | None) -> tuple[int | None, str | None]:
        if not text:
            return None, None

        lowered = text.lower()

        if "don't earn anything" in lowered or "do not earn anything" in lowered:
            return 0, "no_income"

        if "don't earn" in lowered or "do not earn" in lowered:
            return 0, "no_income"

        if "unemployed" in lowered and "$" not in text:
            return 0, "unemployed"

        match = _INCOME_NUMERIC_RE.search(text)
        if match:
            return int(match.group(1).replace(",", "")), "numeric"

        return None, "unparsed"

    def _parse_occupation_from_income_response(self, text: str | None) -> str | None:
        if not text:
            return None

        match = _OCCUPATION_FROM_INCOME_RE.search(text)
        if not match:
            return None

        return match.group(1).strip()

    def _choose_occupation_text(
        self,
        occupation_summary_raw: str | None,
        occupation_chat_raw: str | None,
        occupation_from_income_raw: str | None,
    ) -> str | None:
        if occupation_summary_raw:
            return occupation_summary_raw
        if occupation_chat_raw:
            return occupation_chat_raw
        if occupation_from_income_raw:
            return occupation_from_income_raw
        return None

    def _extract_education_events(
        self,
        collected: ParticipantCollectionResult,
    ) -> list[str]:
        return [
            event.text
            for event in collected.timeline_events
            if _GRADUATED_RE.search(event.text)
        ]