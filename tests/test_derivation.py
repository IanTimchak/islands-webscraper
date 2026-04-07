from scraper.models.normalized import NormalizedParticipant
from scraper.services.derivation import DerivationService


def test_derive_analysis_row_immigrant_other_island() -> None:
    service = DerivationService(
        {
            "Vardo": 0,
            "Shinobi": 1,
        }
    )

    normalized = NormalizedParticipant(
        village_name="Vardo",
        village_id=0,
        island_id=0,
        islander_id="x1",
        islander_name="Test Person",
        age=32,
        current_village="Vardo",
        birth_village="Shinobi",
        education_events=["Graduated from University"],
    )

    row = service.derive_analysis_row(normalized)

    assert row.current_island_id == 0
    assert row.birth_island_id == 1
    assert row.immigrant_other_island is True
    assert row.latest_education_event == "Graduated from University"
    assert row.education_label == "university"


def test_derive_analysis_row_no_education_events() -> None:
    service = DerivationService({"Vardo": 0})

    normalized = NormalizedParticipant(
        village_name="Vardo",
        village_id=0,
        island_id=0,
        islander_id="x1",
        islander_name="Test Person",
        current_village="Vardo",
        birth_village="Vardo",
        education_events=[],
    )

    row = service.derive_analysis_row(normalized)

    assert row.immigrant_other_island is False
    assert row.latest_education_event is None
    assert row.education_label == "no_graduation_event"