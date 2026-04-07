from __future__ import annotations

from scraper.models.normalized import (
    ChatQuestionSpec,
    CollectionPlan,
    ParticipantCollectionResult,
    SummaryFieldSpec,
)
from scraper.models.pages import IslanderPage, VillagePage
from scraper.services.collection import Collector
from scraper.services.progress import NullProgressReporter, ProgressReporter


class DataCollectionService:
    """
    Generic participant-level collection service.

    This service is intentionally a tool, not a study-specific solution.
    It collects:
    - configurable summary fields
    - optional raw timeline events
    - configurable chat questions
    """

    def __init__(
        self,
        collector: Collector,
        progress: ProgressReporter | None = None,
    ) -> None:
        self.collector = collector
        self.progress = progress or NullProgressReporter()

    def collect_participant(
        self,
        village: VillagePage,
        islander_id: str,
        plan: CollectionPlan,
    ) -> ParticipantCollectionResult:
        # fetches the latest islander page using the proper village context
        islander = self.collector.fetch_islander(
            village=village,
            islander_id=islander_id,
        )

        self.progress.emit(0, f"Collecting participant: {islander.name} ({islander.islander_id})")

        summary_data: dict[str, object] = {}
        if plan.include_summary:
            summary_data = self._collect_summary_fields(islander, plan.summary_fields)

        timeline_events = islander.timeline_events if plan.include_timeline else []

        chat_data = self._collect_chat_questions(islander, plan.chat_questions)

        return ParticipantCollectionResult(
            village_name=village.village_name,
            village_id=village.village_id,
            island_id=village.island_id,
            islander_id=islander.islander_id,
            islander_name=islander.name,
            islander=islander,
            summary_data=summary_data,
            chat_data=chat_data,
            timeline_events=timeline_events,
        )

    def _collect_summary_fields(
        self,
        islander: IslanderPage,
        fields: list[SummaryFieldSpec],
    ) -> dict[str, object]:
        result: dict[str, object] = {}

        for field_spec in fields:
            self.progress.emit(
                1,
                f"Collecting summary field '{field_spec.key}' from '{field_spec.source}'",
            )

            if not hasattr(islander, field_spec.source):
                if field_spec.required:
                    raise ValueError(
                        f"Required summary source '{field_spec.source}' not found on IslanderPage."
                    )
                result[field_spec.key] = None
                continue

            value = getattr(islander, field_spec.source)

            if field_spec.required and value is None:
                raise ValueError(
                    f"Required summary field '{field_spec.key}' resolved to None."
                )

            result[field_spec.key] = value

        return result

    def _collect_chat_questions(
        self,
        islander: IslanderPage,
        questions: list[ChatQuestionSpec],
    ) -> dict[str, object]:
        result = {}

        for question_spec in questions:
            self.progress.emit(1, f"Asking question '{question_spec.key}'")

            response = self.collector.ask(
                islander=islander,
                question=question_spec.question_text,
            )

            if question_spec.required and not response.response_text.strip():
                raise ValueError(
                    f"Required chat question '{question_spec.key}' returned an empty response."
                )

            result[question_spec.key] = response

        return result