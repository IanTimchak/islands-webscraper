from scraper.models.normalized import ParticipantCollectionResult
from scraper.models.pages import ChatResponse, IslanderPage, TimelineEvent
from scraper.services.normalization import NormalizationService


def test_normalize_participant_basic() -> None:
    collected = ParticipantCollectionResult(
        village_name="Vardo",
        village_id=0,
        island_id=0,
        islander_id="j4vw2wjwr6",
        islander_name="Kristjana Blomgren",
        islander=IslanderPage(
            islander_id="j4vw2wjwr6",
            name="Kristjana Blomgren",
        ),
        summary_data={
            "age": 32,
            "current_residence": "Lives in Vardo 516",
            "money_summary": "$3,481",
            "occupation_summary": "Waiter",
        },
        chat_data={
            "birth_village": ChatResponse(
                chatid="c1",
                question="Which village were you born in?",
                response_text="I was born in Shinobi.",
            ),
            "income": ChatResponse(
                chatid="c1",
                question="What is your income?",
                response_text="I earn around $29 a day as a waiter.",
            ),
        },
        timeline_events=[
            TimelineEvent(age_stage=18, date_code="01/100", text="Graduated from High School"),
            TimelineEvent(age_stage=22, date_code="01/104", text="Graduated from University"),
        ],
    )

    service = NormalizationService()
    normalized = service.normalize_participant(collected)

    assert normalized.age == 32
    assert normalized.current_residence_raw == "Lives in Vardo 516"
    assert normalized.current_village == "Vardo"
    assert normalized.current_house_number == 516
    assert normalized.money_summary_raw == "$3,481"
    assert normalized.money_summary_value == 3481
    assert normalized.birth_village_raw == "I was born in Shinobi."
    assert normalized.birth_village == "Shinobi"
    assert normalized.income_response_raw == "I earn around $29 a day as a waiter."
    assert normalized.income_numeric == 29
    assert normalized.income_text_normalized == "numeric"
    assert normalized.occupation_summary_raw == "Waiter"
    assert normalized.occupation_from_income_raw == "waiter"
    assert normalized.occupation_text == "Waiter"
    assert normalized.education_events == [
        "Graduated from High School",
        "Graduated from University",
    ]


def test_normalize_participant_zero_income_phrase() -> None:
    collected = ParticipantCollectionResult(
        village_name="Vardo",
        village_id=0,
        island_id=0,
        islander_id="x1",
        islander_name="Test Person",
        islander=IslanderPage(
            islander_id="x1",
            name="Test Person",
        ),
        summary_data={},
        chat_data={
            "income": ChatResponse(
                chatid="c1",
                question="What is your income?",
                response_text="I don't earn anything.",
            ),
        },
        timeline_events=[],
    )

    service = NormalizationService()
    normalized = service.normalize_participant(collected)

    assert normalized.income_numeric == 0
    assert normalized.income_text_normalized == "no_income"