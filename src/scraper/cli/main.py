from __future__ import annotations

"""Main CLI entry point for the Islands webscraper.

This module is intentionally the most visible developer surface in the project.
It should therefore do three things well:

1. expose the available workflows clearly,
2. document the common extension points for new studies,
3. keep console rendering separate from workflow orchestration.

A recurring maintenance pain point in earlier versions of this file was that
study-specific console output lived inline inside otherwise generic commands.
That made the CLI harder to scan and forced future studies to edit command
bodies just to change presentation. The refactor below keeps the workflow
logic intact, but moves most user-facing formatting into small renderer helpers
and explicit field lists so the file stays easier to extend.
"""

from datetime import datetime
from uuid import uuid4
from typing import Any, Iterable, Mapping

import typer

from scraper import config
from scraper.auth_browser import (
    SUPPORTED_BROWSERS,
    build_cookie_header_for_domain,
    open_login_page,
)
from scraper.auth_env import clear_auth_cookie, get_auth_cookie, set_auth_cookie
from scraper.client.session import IslandsSession
from scraper.models.normalized import (
    ChatQuestionSpec,
    CollectionPlan,
    SamplingPlan,
    SummaryFieldSpec,
)
from scraper.services.auth import require_auth_present_and_fresh, validate_current_auth
from scraper.services.collection import Collector
from scraper.services.data_collection import DataCollectionService
from scraper.services.derivation import DerivationService
from scraper.services.normalization import NormalizationService
from scraper.services.persistence import PersistenceService
from scraper.services.progress import ConsoleProgressReporter
from scraper.services.sampling import SamplingService
from scraper.services.workflow import CollectionWorkflow
from scraper.study_profile import PLACE_TO_ISLAND

app = typer.Typer(
    help=(
        "Islands webscraper CLI.\n\n"
        "This tool helps you authenticate, inspect simulator data, sample households, "
        "collect participant data, normalize results, derive analysis rows, and save "
        "run-scoped outputs."
    ),
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Top-level CLI group."""
    return


@app.command()
def hello() -> None:
    """Sanity check that the CLI entry point is working."""
    typer.echo("islands-webscraper is set up")


# auth helpers
def ensure_auth_or_exit() -> None:
    """Exit with a friendly message if auth is missing or stale."""
    try:
        require_auth_present_and_fresh()
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)


def _slugify(value: str) -> str:
    """Turn a label into a simple file-safe slug for run ids."""
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.strip())


def _timestamp_for_run_id() -> str:
    """Timestamp prefix used in generated run ids."""
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


def _build_village_run_id(village_name: str, n: int, seed: int) -> str:
    """Build a descriptive run id for one village workflow."""
    ts = _timestamp_for_run_id()
    suffix = uuid4().hex[:8]
    return f"{ts}_village-{_slugify(village_name)}_n-{n}_seed-{seed}_{suffix}"


def _build_participant_run_id(village_name: str, islander_id: str) -> str:
    """Build a descriptive run id for one participant workflow."""
    ts = _timestamp_for_run_id()
    suffix = uuid4().hex[:8]
    return f"{ts}_participant-{_slugify(islander_id)}_village-{_slugify(village_name)}_{suffix}"


def _build_study_run_id(village_names: list[str], n: int, seed: int) -> str:
    """Build a descriptive run id for a multi-village study workflow."""
    ts = _timestamp_for_run_id()
    suffix = uuid4().hex[:8]
    villages_part = "-".join(_slugify(name) for name in village_names[:3])
    if len(village_names) > 3:
        villages_part += f"-plus{len(village_names) - 3}"
    return f"{ts}_study_{villages_part}_n-{n}_seed-{seed}_{suffix}"


def _parse_question_specs(question: list[str]) -> list[ChatQuestionSpec]:
    """Parse repeated key=question-text CLI options into ChatQuestionSpec objects."""
    chat_specs: list[ChatQuestionSpec] = []

    for raw_question in question:
        if "=" not in raw_question:
            raise typer.BadParameter(
                f"Question spec must look like key=Question text, got: {raw_question!r}"
            )

        key, question_text = raw_question.split("=", 1)
        key = key.strip()
        question_text = question_text.strip()

        if not key or not question_text:
            raise typer.BadParameter(
                f"Question spec must include both key and question text, got: {raw_question!r}"
            )

        chat_specs.append(
            ChatQuestionSpec(
                key=key,
                question_text=question_text,
                required=False,
            )
        )

    return chat_specs


def _build_collection_plan(
    summary_field: list[str],
    question: list[str],
    include_timeline: bool,
) -> CollectionPlan:
    """Build a generic collection plan from CLI arguments."""
    summary_specs = [
        SummaryFieldSpec(key=field_name, source=field_name, required=False)
        for field_name in summary_field
    ]

    chat_specs = _parse_question_specs(question)

    return CollectionPlan(
        include_summary=True,
        include_timeline=include_timeline,
        summary_fields=summary_specs,
        chat_questions=chat_specs,
    )


def _build_study_default_collection_plan(include_timeline: bool = True) -> CollectionPlan:
    """
    Build the current study's default collection plan.

    This is the small convenience layer for the immigrant / income study.
    It keeps the core collection engine generic while sparing you from
    retyping the same fields and questions every run.
    """
    return CollectionPlan(
        include_summary=True,
        include_timeline=include_timeline,
        summary_fields=[
            SummaryFieldSpec(key="age", source="age", required=False),
            SummaryFieldSpec(key="current_residence", source="current_residence", required=False),
            SummaryFieldSpec(key="money_summary", source="money_summary", required=False),
            SummaryFieldSpec(key="occupation_summary", source="occupation_summary", required=False),
        ],
        chat_questions=[
            ChatQuestionSpec(
                key="birth_village",
                question_text="Which village were you born in?",
                required=False,
            ),
            ChatQuestionSpec(
                key="income",
                question_text="What is your income?",
                required=False,
            ),
        ],
    )


# -----------------------------------------------------------------------------
# Console rendering helpers
# -----------------------------------------------------------------------------
#
# The command functions below should primarily orchestrate the workflow:
# validate auth, build plans, call services, and persist results.
#
# Any output that is mainly "how we print a result" belongs in helpers in this
# section. Keeping these renderers centralized makes the command bodies shorter
# and makes study-specific presentation easier to swap out later.
# -----------------------------------------------------------------------------


STUDY_DEFAULT_QUESTION_SPECS = [
    "birth_village=Which village were you born in?",
    "income=What is your income?",
]

STUDY_NORMALIZED_FIELD_NAMES = [
    "age",
    "current_residence_raw",
    "current_village",
    "current_house_number",
    "money_summary_raw",
    "money_summary_value",
    "birth_village_raw",
    "birth_village",
    "income_response_raw",
    "income_numeric",
    "income_text_normalized",
    "occupation_from_income_raw",
    "occupation_summary_raw",
    "occupation_chat_raw",
    "occupation_text",
]

STUDY_ANALYSIS_DERIVED_FIELD_NAMES = [
    "age",
    "current_village",
    "current_island_id",
    "birth_village",
    "birth_island_id",
    "immigrant_other_island",
]

STUDY_ANALYSIS_CARRY_FIELD_NAMES = [
    "current_residence_raw",
    "money_summary_raw",
    "money_summary_value",
    "income_response_raw",
    "income_numeric",
    "income_text_normalized",
    "occupation_text",
]

STUDY_ANALYSIS_EDUCATION_FIELD_NAMES = [
    "latest_education_event",
    "education_label",
]


def _echo_blank() -> None:
    """Print one blank line to visually separate output sections."""
    typer.echo("")


def _echo_title(title: str) -> None:
    """Print a section title with a leading blank line for readability."""
    _echo_blank()
    typer.echo(title)


def _echo_key_value(label: str, value: Any, *, indent: str = "") -> None:
    """Print one label/value line with optional indentation."""
    typer.echo(f"{indent}{label}: {value}")


def _echo_key_values(
    pairs: Iterable[tuple[str, Any]],
    *,
    indent: str = "",
) -> None:
    """Print a sequence of (label, value) pairs in order."""
    for label, value in pairs:
        _echo_key_value(label, value, indent=indent)


def _echo_mapping(
    title: str,
    mapping: Mapping[str, Any],
    *,
    indent: str = "  ",
    empty_text: str = "<none>",
) -> None:
    """Print a mapping under a titled section, preserving insertion order."""
    _echo_title(title)
    if not mapping:
        typer.echo(f"{indent}{empty_text}")
        return

    for key, value in mapping.items():
        _echo_key_value(key, value, indent=indent)


def _echo_object_fields(
    title: str,
    obj: Any,
    field_names: Iterable[str],
    *,
    indent: str = "  ",
) -> None:
    """Print selected attributes from an object using an explicit field order."""
    _echo_title(title)
    for field_name in field_names:
        _echo_key_value(field_name, getattr(obj, field_name, None), indent=indent)


def _response_text(response: Any) -> str:
    """Extract a printable response string from a chat response-like object."""
    text = getattr(response, "response_text", response)
    return text if text not in (None, "") else "<empty>"


def _echo_chat_mapping(
    title: str,
    mapping: Mapping[str, Any],
    *,
    indent: str = "  ",
    empty_text: str = "<none>",
) -> None:
    """Print chat responses while hiding the concrete response object shape."""
    _echo_title(title)
    if not mapping:
        typer.echo(f"{indent}{empty_text}")
        return

    for key, response in mapping.items():
        _echo_key_value(key, _response_text(response), indent=indent)


def _render_participant_collection_result(result: Any) -> None:
    """Render a collected participant result in a generic, plan-driven way."""
    _echo_title("Participant collection result")
    _echo_key_values(
        [
            ("Village", result.village_name),
            ("Village ID", result.village_id),
            ("Island ID", result.island_id),
            ("Name", result.islander_name),
            ("Islander ID", result.islander_id),
        ]
    )
    _echo_mapping("Summary data", result.summary_data)
    _echo_chat_mapping("Chat data", result.chat_data)
    _echo_blank()
    typer.echo(f"Timeline events: {len(result.timeline_events)}")


def _render_normalized_participant(result: Any) -> None:
    """Render the normalized participant view used by the current study."""
    _echo_title("Normalized participant")
    _echo_key_values(
        [
            ("Village", result.village_name),
            ("Village ID", result.village_id),
            ("Island ID", result.island_id),
            ("Name", result.islander_name),
            ("Islander ID", result.islander_id),
        ]
    )
    _echo_object_fields("Normalized fields", result, STUDY_NORMALIZED_FIELD_NAMES)

    _echo_blank()
    typer.echo(f"Education events: {len(result.education_events)}")
    for event_text in result.education_events[:10]:
        typer.echo(f"  - {event_text}")


def _render_analysis_row(result: Any) -> None:
    """Render the study's derived analysis row in grouped sections."""
    _echo_title("Analysis row")
    _echo_key_values(
        [
            ("Village", result.village_name),
            ("Village ID", result.village_id),
            ("Island ID", result.island_id),
            ("Name", result.islander_name),
            ("Islander ID", result.islander_id),
        ]
    )
    _echo_object_fields("Derived fields", result, STUDY_ANALYSIS_DERIVED_FIELD_NAMES)
    _echo_object_fields("Carry-through fields", result, STUDY_ANALYSIS_CARRY_FIELD_NAMES)
    _echo_object_fields("Education", result, STUDY_ANALYSIS_EDUCATION_FIELD_NAMES)


def _render_sample_village_result(result: Any) -> None:
    """Render the output of the sampling-only village workflow."""
    _echo_key_values(
        [
            ("Village", result.village_name),
            ("Village ID", result.village_id),
            ("Island ID", result.island_id),
            ("Frame size", result.frame_size),
            ("Primary households", result.primary_household_ids),
            ("Reserve households", result.reserve_household_ids),
        ]
    )

    _echo_blank()
    for sampled in result.sampled_households:
        header = f"House internal_id={sampled.house_id}"
        if sampled.display_house_number is not None:
            header += f", display={sampled.display_house_number}"
        typer.echo(header)
        typer.echo(f"  residents={len(sampled.residents)}")
        typer.echo(f"  eligible_adults={len(sampled.eligible_adults)}")
        typer.echo(f"  status={sampled.status}")

        if sampled.selected_adult is not None:
            typer.echo(
                f"  selected={sampled.selected_adult.name} "
                f"(age={sampled.selected_adult.age}, islander_id={sampled.selected_adult.islander_id})"
            )
        else:
            typer.echo("  selected=None")

        _echo_blank()


def _render_village_collection_summary(
    result: Any,
    *,
    include_collected_payloads: bool = False,
) -> None:
    """Render a village workflow summary with optional collected participant details."""
    _echo_title("Summary")
    summary_pairs = [
        ("Village", result.village_name),
        ("Village ID", getattr(result, "village_id", None)),
        ("Island ID", getattr(result, "island_id", None)),
        ("Frame size", getattr(result, "frame_size", None)),
        ("Processed households", len(result.processed_households)),
        ("Reserve exhausted", result.exhausted_reserve),
    ]

    if hasattr(result, "primary_household_ids"):
        summary_pairs.insert(4, ("Primary households", result.primary_household_ids))
    if hasattr(result, "reserve_household_ids"):
        summary_pairs.insert(5, ("Reserve households", result.reserve_household_ids))
    if hasattr(result, "completed_participants"):
        summary_pairs.append(("Completed participants", len(result.completed_participants)))
    if hasattr(result, "collected_participant_results"):
        summary_pairs.append(
            ("Completed collected participants", len(result.collected_participant_results))
        )

    _echo_key_values(summary_pairs)

    if getattr(result, "completed_participants", None):
        _echo_title("Completed participants")
        for idx, participant in enumerate(result.completed_participants, start=1):
            adult = participant.selected_adult
            line = (
                f"{idx}. {adult.name} | age={adult.age} | islander_id={adult.islander_id} "
                f"| house_id={participant.house_id}"
            )
            if participant.display_house_number is not None:
                line += f" | display_house={participant.display_house_number}"
            typer.echo(line)

    if include_collected_payloads and getattr(result, "collected_participant_results", None):
        _echo_title("Collected participants")
        for idx, participant in enumerate(result.collected_participant_results, start=1):
            typer.echo(f"{idx}. {participant.islander_name} | islander_id={participant.islander_id}")

            if participant.summary_data:
                typer.echo("   Summary:")
                for key, value in participant.summary_data.items():
                    typer.echo(f"     {key}: {value}")

            if participant.chat_data:
                typer.echo("   Chat:")
                for key, response in participant.chat_data.items():
                    typer.echo(f"     {key}: {_response_text(response)}")


def _render_participant_save_summary(output_dir: Any) -> None:
    """Render the standard save receipt for one participant run."""
    typer.echo(f"Saved outputs to: {output_dir}")
    typer.echo("Saved participant collection result to raw/participant_collection.jsonl")
    typer.echo("Saved normalized participant to normalized/participants.jsonl")
    typer.echo("Saved analysis row to analysis/analysis_rows.jsonl and analysis/analysis_rows.csv")


def _render_village_save_summary(output_dir: Any) -> None:
    """Render the standard save receipt for one village run."""
    typer.echo(f"Saved outputs to: {output_dir}")
    typer.echo("Saved sampling run metadata.")
    typer.echo("Saved processed household audit records.")
    typer.echo("Saved participant collection records.")
    typer.echo("Saved normalized participant records.")
    typer.echo("Saved analysis rows to JSONL and CSV.")


def _render_study_save_summary(output_dir: Any, village_count: int, analysis_row_count: int) -> None:
    """Render the standard save receipt for a multi-village study run."""
    typer.echo(f"Saved study outputs to: {output_dir}")
    typer.echo(f"Villages processed: {village_count}")
    typer.echo(f"Total analysis rows: {analysis_row_count}")


def _render_resume_summary(output_dir: Any, analysis_row_count: int) -> None:
    """Render the standard receipt after resuming a study run."""
    typer.echo(f"Resumed study outputs in: {output_dir}")
    typer.echo(f"Total new analysis rows written in this resume pass: {analysis_row_count}")


# auth commands
@app.command("auth-login")
def auth_login(
    browser: str = typer.Option(..., help="Browser to use for guided login: chrome or firefox."),
    no_open: bool = typer.Option(
        False,
        help="Do not automatically open the site in the browser.",
    ),
) -> None:
    """
    Open the site, let you log in manually, then import cookies from the selected browser.

    This writes the authenticated cookie header into .env and validates it once.
    """
    browser = browser.lower().strip()
    if browser not in SUPPORTED_BROWSERS:
        raise typer.BadParameter(
            f"Unsupported browser '{browser}'. Use one of: {sorted(SUPPORTED_BROWSERS)}"
        )

    base_url = config.settings.islands_base_url.rstrip("/")
    login_url = f"{base_url}/"

    typer.echo(f"Selected browser: {browser}")
    typer.echo(f"Site: {login_url}")

    if not no_open:
        typer.echo("Opening login page in your browser...")
        open_login_page(login_url, browser)

    typer.echo("")
    typer.echo("Please log in fully in that browser window.")
    typer.echo("After login is complete, return here and press Enter.")
    input()

    typer.echo("Importing cookies from browser profile...")

    try:
        cookie_header = build_cookie_header_for_domain(browser=browser, base_url=base_url)
    except Exception as exc:
        typer.echo(f"Cookie import failed: {exc}")
        typer.echo("Fallback: run 'islands auth-set-cookie' and paste the Cookie header manually.")
        raise typer.Exit(code=1)

    set_auth_cookie(cookie_header)

    typer.echo("Stored auth in .env. Validating session...")
    status = validate_current_auth()

    if status.is_valid:
        typer.echo(f"Success: {status.message}")
        return

    typer.echo(f"Validation failed: {status.message}")
    typer.echo("You may not have finished logging in, or cookie import may not have worked.")
    typer.echo("Fallback: run 'islands auth-set-cookie'.")
    raise typer.Exit(code=1)


@app.command("auth-set-cookie")
def auth_set_cookie() -> None:
    """
    Manually paste a Cookie header and store it in .env.

    This is the fallback path when browser cookie import does not work.
    """
    typer.echo("Paste the authenticated Cookie header value.")
    typer.echo("Example: PHPSESSID=...; other_cookie=...")
    cookie_header = typer.prompt("Cookie header", hide_input=False).strip()

    if not cookie_header:
        typer.echo("No cookie header provided.")
        raise typer.Exit(code=1)

    set_auth_cookie(cookie_header)

    typer.echo("Stored auth in .env. Validating session...")
    status = validate_current_auth()

    if status.is_valid:
        typer.echo(f"Success: {status.message}")
        return

    typer.echo(f"Validation failed: {status.message}")
    raise typer.Exit(code=1)


@app.command("auth-test")
def auth_test() -> None:
    """Run an explicit live auth check against the currently stored cookie."""
    cookie = get_auth_cookie()
    if not cookie:
        typer.echo("No ISLANDS_COOKIE_HEADER found in .env.")
        raise typer.Exit(code=1)

    status = validate_current_auth()
    if status.is_valid:
        typer.echo(f"Valid: {status.message}")
        return

    typer.echo(f"Invalid: {status.message}")
    raise typer.Exit(code=1)


@app.command("auth-clear")
def auth_clear() -> None:
    """Remove stored auth values from .env."""
    clear_auth_cookie()
    typer.echo("Cleared Islands auth values from .env.")


# inspection commands
@app.command("fetch-village")
def fetch_village(
    village_name: str = typer.Argument(..., help="Village name to fetch, for example Vardo."),
) -> None:
    """Fetch and parse one village page, then print basic metadata and household count."""
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        village = collector.fetch_village(village_name)

    typer.echo(f"Village: {village.village_name}")
    typer.echo(f"Village ID: {village.village_id}")
    typer.echo(f"Island ID: {village.island_id}")
    typer.echo(f"Households found: {len(village.house_ids)}")


@app.command("fetch-household")
def fetch_household(
    village_name: str = typer.Option(..., help="Village name where the household is located."),
    house_id: int = typer.Option(..., help="Internal household id from the village frame."),
) -> None:
    """Fetch and parse one household, then print its residents."""
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        village = collector.fetch_village(village_name)
        household = collector.fetch_household(village=village, house_id=house_id)

    typer.echo(f"Village: {village.village_name}")
    typer.echo(f"Village ID: {household.village_id}")
    typer.echo(f"Internal House ID: {household.house_id}")

    if household.display_house_number is not None:
        typer.echo(f"Displayed House Number: {household.display_house_number}")

    typer.echo(f"Residents found: {len(household.residents)}")
    for idx, resident in enumerate(household.residents, start=1):
        typer.echo(
            f"{idx}. {resident.name} | age={resident.age} | islander_id={resident.islander_id}"
        )


@app.command("fetch-islander")
def fetch_islander(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
) -> None:
    """Fetch and parse one islander page, then print its main parsed fields."""
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        village = collector.fetch_village(village_name)
        islander = collector.fetch_islander(village=village, islander_id=islander_id)

    typer.echo(f"Name: {islander.name}")
    typer.echo(f"Islander ID: {islander.islander_id}")
    typer.echo(f"Chat ID: {islander.chatid}")
    typer.echo(f"Awake: {islander.awake}")
    typer.echo(f"Age: {islander.age}")
    typer.echo(f"Occupation summary: {islander.occupation_summary}")
    typer.echo(f"Money summary: {islander.money_summary}")
    typer.echo(f"Current residence: {islander.current_residence}")
    typer.echo(f"Timeline events: {len(islander.timeline_events)}")

    for event in islander.timeline_events[:5]:
        typer.echo(f"- age_stage={event.age_stage} | {event.date_code} | {event.text}")


@app.command("consent")
def consent(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
) -> None:
    """Request consent for one islander and print the parsed consent response."""
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        village = collector.fetch_village(village_name)
        islander = collector.fetch_islander(village=village, islander_id=islander_id)
        consent_response = collector.request_consent(islander)

    typer.echo(f"Islander ID: {consent_response.islander_id}")
    typer.echo(f"Outcome: {consent_response.outcome}")
    typer.echo(f"Timestamp: {consent_response.timestamp_text}")
    typer.echo(f"Message: {consent_response.message}")


@app.command("ask")
def ask(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
    question: str = typer.Option(..., help="Question text to send through the chat endpoint."),
) -> None:
    """Ask one free-form chat question and print the parsed chat response."""
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        village = collector.fetch_village(village_name)
        islander = collector.fetch_islander(village=village, islander_id=islander_id)
        response = collector.ask(islander=islander, question=question)

    typer.echo(f"Question: {response.question}")
    typer.echo(f"Chat ID: {response.chatid}")
    typer.echo("")
    typer.echo("Response:")
    typer.echo(response.response_text or "<empty>")
    typer.echo("")
    typer.echo(f"State updates: {len(response.state_updates)}")
    for key, value in response.state_updates.items():
        typer.echo(f"- {key}={value}")


# sampling commands
@app.command("sample-village")
def sample_village(
    village_name: str = typer.Option(..., help="Village name to sample from."),
    n: int = typer.Option(..., help="Number of primary households to sample."),
    reserve_n: int = typer.Option(20, help="Number of reserve households to pre-generate."),
    seed: int = typer.Option(401, help="Seed for reproducible random sampling."),
    min_age: int = typer.Option(21, help="Minimum age for adult eligibility."),
) -> None:
    """
    Run the household/adult sampling slice for one village.

    This command does not request consent or collect chat data.
    It only samples households and selects one eligible adult per household.
    """
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        sampling = SamplingService(collector)

        village = collector.fetch_village(village_name)

        plan = SamplingPlan(
            households_per_village=n,
            reserve_households_per_village=reserve_n,
            adults_only_min_age=min_age,
            seed=seed,
        )

        result = sampling.sample_village(village=village, plan=plan)

    _render_sample_village_result(result)


@app.command("collect-village")
def collect_village(
    village_name: str = typer.Option(..., help="Village name to collect from."),
    n: int = typer.Option(..., help="Target completed participants."),
    reserve_n: int = typer.Option(20, help="Number of reserve households to pre-generate."),
    seed: int = typer.Option(401, help="Seed for reproducible random sampling."),
    min_age: int = typer.Option(21, help="Minimum age for adult eligibility."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """
    Run the consent-aware village workflow for one village.

    This command:
    - samples households
    - picks one eligible adult
    - requests consent
    - uses reserves on failure
    - stops when the target completed count is reached

    It does not yet collect configurable participant data.
    """
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        sampling = SamplingService(collector)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        workflow = CollectionWorkflow(
            collector=collector,
            sampling=sampling,
            data_collection=data_collection,
            progress=progress,
        )

        village = collector.fetch_village(village_name)

        collection_plan = CollectionPlan(
            include_summary=False,
            include_timeline=False,
            summary_fields=[],
            chat_questions=[],
        )

        sampling_plan = SamplingPlan(
            households_per_village=n,
            reserve_households_per_village=reserve_n,
            adults_only_min_age=min_age,
            seed=seed,
        )

        result = workflow.collect_village(
            village=village,
            sampling_plan=sampling_plan,
            collection_plan=collection_plan,
        )
        progress.stop()

    _render_village_collection_summary(result)


# collection commands
@app.command("collect-participant")
def collect_participant(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
    summary_field: list[str] = typer.Option(
        [],
        help="Summary field source names to collect. Repeat this option for multiple fields.",
    ),
    question: list[str] = typer.Option(
        [],
        help='Chat question specs in the form key="Question text". Repeat for multiple questions.',
    ),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """
    Collect raw-ish participant evidence for one islander.

    This is the generic participant collection tool:
    - configurable summary fields
    - configurable chat questions
    - optional timeline inclusion
    """
    ensure_auth_or_exit()

    plan = _build_collection_plan(
        summary_field=summary_field,
        question=question,
        include_timeline=include_timeline,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )

        village = collector.fetch_village(village_name)
        result = data_collection.collect_participant(
            village=village,
            islander_id=islander_id,
            plan=plan,
        )
        progress.stop()

    _render_participant_collection_result(result)


@app.command("collect-study-default-participant")
def collect_study_default_participant(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """
    Collect one participant using the current study defaults.

    Current defaults:
    - summary fields: age, current_residence, money_summary, occupation_summary
    - chat questions: birth_village, income
    """
    ensure_auth_or_exit()

    plan = _build_study_default_collection_plan(include_timeline=include_timeline)

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )

        village = collector.fetch_village(village_name)
        result = data_collection.collect_participant(
            village=village,
            islander_id=islander_id,
            plan=plan,
        )
        progress.stop()

    _render_participant_collection_result(result)


@app.command("collect-and-normalize-participant")
def collect_and_normalize_participant(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
    summary_field: list[str] = typer.Option(
        [],
        help="Summary field source names to collect. Repeat this option for multiple fields.",
    ),
    question: list[str] = typer.Option(
        [],
        help='Chat question specs in the form key="Question text". Repeat for multiple questions.',
    ),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """Collect one participant using a configurable plan, then normalize the result."""
    ensure_auth_or_exit()

    plan = _build_collection_plan(
        summary_field=summary_field,
        question=question,
        include_timeline=include_timeline,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()

        village = collector.fetch_village(village_name)
        collected = data_collection.collect_participant(
            village=village,
            islander_id=islander_id,
            plan=plan,
        )
        normalized = normalization.normalize_participant(collected)
        progress.stop()

    _render_normalized_participant(normalized)


@app.command("collect-study-default-and-normalize-participant")
def collect_study_default_and_normalize_participant(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """Collect and normalize one participant using the current study defaults."""
    ensure_auth_or_exit()

    plan = _build_study_default_collection_plan(include_timeline=include_timeline)

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()

        village = collector.fetch_village(village_name)
        collected = data_collection.collect_participant(
            village=village,
            islander_id=islander_id,
            plan=plan,
        )
        normalized = normalization.normalize_participant(collected)
        progress.stop()

    _render_normalized_participant(normalized)


@app.command("collect-normalize-derive-participant")
def collect_normalize_derive_participant(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
    summary_field: list[str] = typer.Option(
        [],
        help="Summary field source names to collect. Repeat this option for multiple fields.",
    ),
    question: list[str] = typer.Option(
        [],
        help='Chat question specs in the form key="Question text". Repeat for multiple questions.',
    ),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """Collect, normalize, and derive one participant using a configurable plan."""
    ensure_auth_or_exit()

    plan = _build_collection_plan(
        summary_field=summary_field,
        question=question,
        include_timeline=include_timeline,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()
        derivation = DerivationService(PLACE_TO_ISLAND)

        village = collector.fetch_village(village_name)
        collected = data_collection.collect_participant(
            village=village,
            islander_id=islander_id,
            plan=plan,
        )
        normalized = normalization.normalize_participant(collected)
        analysis_row = derivation.derive_analysis_row(normalized)
        progress.stop()

    _render_analysis_row(analysis_row)


@app.command("collect-study-default-and-derive-participant")
def collect_study_default_and_derive_participant(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """Collect, normalize, and derive one participant using the current study defaults."""
    ensure_auth_or_exit()

    plan = _build_study_default_collection_plan(include_timeline=include_timeline)

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()
        derivation = DerivationService(PLACE_TO_ISLAND)

        village = collector.fetch_village(village_name)
        collected = data_collection.collect_participant(
            village=village,
            islander_id=islander_id,
            plan=plan,
        )
        normalized = normalization.normalize_participant(collected)
        analysis_row = derivation.derive_analysis_row(normalized)
        progress.stop()

    _render_analysis_row(analysis_row)


# save commands
@app.command("collect-normalize-derive-and-save-participant")
def collect_normalize_derive_and_save_participant(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
    summary_field: list[str] = typer.Option(
        [],
        help="Summary field source names to collect. Repeat this option for multiple fields.",
    ),
    question: list[str] = typer.Option(
        [],
        help='Chat question specs in the form key="Question text". Repeat for multiple questions.',
    ),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
    run_id: str | None = typer.Option(
        None,
        help="Optional run id. If omitted, a new run directory is created.",
    ),
) -> None:
    """Collect, normalize, derive, and save one participant using a configurable plan."""
    ensure_auth_or_exit()

    plan = _build_collection_plan(
        summary_field=summary_field,
        question=question,
        include_timeline=include_timeline,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()
        derivation = DerivationService(PLACE_TO_ISLAND)

        resolved_run_id = run_id or _build_participant_run_id(
            village_name=village_name,
            islander_id=islander_id,
        )

        persistence = PersistenceService(
            data_dir=config.settings.data_dir,
            run_id=resolved_run_id,
            save_debug_payloads=config.settings.save_debug_payloads,
        )

        village = collector.fetch_village(village_name)
        collected = data_collection.collect_participant(
            village=village,
            islander_id=islander_id,
            plan=plan,
        )
        normalized = normalization.normalize_participant(collected)
        analysis_row = derivation.derive_analysis_row(normalized)

        persistence.persist_participant_collection(collected)
        persistence.persist_normalized_participant(normalized)
        persistence.append_analysis_row_jsonl(analysis_row)
        persistence.write_analysis_rows_csv([analysis_row])
        progress.stop()

    _render_participant_save_summary(persistence.output_dir)


@app.command("collect-study-default-and-save-participant")
def collect_study_default_and_save_participant(
    village_name: str = typer.Option(..., help="Village name where the islander was found."),
    islander_id: str = typer.Option(..., help="Islander id."),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
    run_id: str | None = typer.Option(
        None,
        help="Optional run id. If omitted, a new run directory is created.",
    ),
) -> None:
    """Collect, normalize, derive, and save one participant using the current study defaults."""
    ensure_auth_or_exit()

    plan = _build_study_default_collection_plan(include_timeline=include_timeline)

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()
        derivation = DerivationService(PLACE_TO_ISLAND)

        resolved_run_id = run_id or _build_participant_run_id(
            village_name=village_name,
            islander_id=islander_id,
        )

        persistence = PersistenceService(
            data_dir=config.settings.data_dir,
            run_id=resolved_run_id,
            save_debug_payloads=config.settings.save_debug_payloads,
        )

        village = collector.fetch_village(village_name)
        collected = data_collection.collect_participant(
            village=village,
            islander_id=islander_id,
            plan=plan,
        )
        normalized = normalization.normalize_participant(collected)
        analysis_row = derivation.derive_analysis_row(normalized)

        persistence.persist_participant_collection(collected)
        persistence.persist_normalized_participant(normalized)
        persistence.append_analysis_row_jsonl(analysis_row)
        persistence.write_analysis_rows_csv([analysis_row])
        progress.stop()

    _render_participant_save_summary(persistence.output_dir)


@app.command("collect-village-data")
def collect_village_data(
    village_name: str = typer.Option(..., help="Village name to collect from."),
    n: int = typer.Option(..., help="Target completed participants."),
    reserve_n: int = typer.Option(20, help="Number of reserve households to pre-generate."),
    seed: int = typer.Option(401, help="Seed for reproducible random sampling."),
    min_age: int = typer.Option(21, help="Minimum age for adult eligibility."),
    summary_field: list[str] = typer.Option(
        [],
        help="Summary field source names to collect. Repeat this option for multiple fields.",
    ),
    question: list[str] = typer.Option(
        [],
        help='Chat question specs in the form key="Question text". Repeat for multiple questions.',
    ),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """
    Run the full configurable village workflow:
    sampling + consent + participant collection.
    """
    ensure_auth_or_exit()

    collection_plan = _build_collection_plan(
        summary_field=summary_field,
        question=question,
        include_timeline=include_timeline,
    )

    sampling_plan = SamplingPlan(
        households_per_village=n,
        reserve_households_per_village=reserve_n,
        adults_only_min_age=min_age,
        seed=seed,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        sampling = SamplingService(collector)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        workflow = CollectionWorkflow(
            collector=collector,
            sampling=sampling,
            data_collection=data_collection,
            progress=progress,
        )

        village = collector.fetch_village(village_name)
        result = workflow.collect_village(
            village=village,
            sampling_plan=sampling_plan,
            collection_plan=collection_plan,
        )
        progress.stop()

    _render_village_collection_summary(result, include_collected_payloads=True)


@app.command("collect-study-default-village")
def collect_study_default_village(
    village_name: str = typer.Option(..., help="Village name to collect from."),
    n: int = typer.Option(..., help="Target completed participants."),
    reserve_n: int = typer.Option(20, help="Number of reserve households to pre-generate."),
    seed: int = typer.Option(401, help="Seed for reproducible random sampling."),
    min_age: int = typer.Option(21, help="Minimum age for adult eligibility."),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """
    Run the full village workflow using the current study defaults.

    Current defaults:
    - summary fields: age, current_residence, money_summary, occupation_summary
    - chat questions: birth_village, income
    """
    ensure_auth_or_exit()

    collection_plan = _build_study_default_collection_plan(include_timeline=include_timeline)

    sampling_plan = SamplingPlan(
        households_per_village=n,
        reserve_households_per_village=reserve_n,
        adults_only_min_age=min_age,
        seed=seed,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        sampling = SamplingService(collector)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        workflow = CollectionWorkflow(
            collector=collector,
            sampling=sampling,
            data_collection=data_collection,
            progress=progress,
        )

        village = collector.fetch_village(village_name)
        result = workflow.collect_village(
            village=village,
            sampling_plan=sampling_plan,
            collection_plan=collection_plan,
        )
        progress.stop()

    _render_village_collection_summary(result, include_collected_payloads=True)


@app.command("collect-village-data-and-save")
def collect_village_data_and_save(
    village_name: str = typer.Option(..., help="Village name to collect from."),
    n: int = typer.Option(..., help="Target completed participants."),
    reserve_n: int = typer.Option(20, help="Number of reserve households to pre-generate."),
    seed: int = typer.Option(401, help="Seed for reproducible random sampling."),
    min_age: int = typer.Option(21, help="Minimum age for adult eligibility."),
    summary_field: list[str] = typer.Option(
        [],
        help="Summary field source names to collect. Repeat this option for multiple fields.",
    ),
    question: list[str] = typer.Option(
        [],
        help='Chat question specs in the form key="Question text". Repeat for multiple questions.',
    ),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
    run_id: str | None = typer.Option(
        None,
        help="Optional run id. If omitted, a new run directory is created.",
    ),
) -> None:
    """Run the full configurable village workflow and save run-scoped outputs."""
    ensure_auth_or_exit()

    collection_plan = _build_collection_plan(
        summary_field=summary_field,
        question=question,
        include_timeline=include_timeline,
    )

    sampling_plan = SamplingPlan(
        households_per_village=n,
        reserve_households_per_village=reserve_n,
        adults_only_min_age=min_age,
        seed=seed,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        sampling = SamplingService(collector)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()
        derivation = DerivationService(PLACE_TO_ISLAND)
        workflow = CollectionWorkflow(
            collector=collector,
            sampling=sampling,
            data_collection=data_collection,
            normalization=normalization,
            derivation=derivation,
            progress=progress,
        )

        resolved_run_id = run_id or _build_village_run_id(
            village_name=village_name,
            n=n,
            seed=seed,
        )

        persistence = PersistenceService(
            data_dir=config.settings.data_dir,
            run_id=resolved_run_id,
            save_debug_payloads=config.settings.save_debug_payloads,
        )

        village = collector.fetch_village(village_name)
        result = workflow.collect_village(
            village=village,
            sampling_plan=sampling_plan,
            collection_plan=collection_plan,
        )

        # keep existing single-village persistence behavior
        from scraper.models.analysis import ProcessedHouseholdRecord, SamplingRunRecord

        persistence.persist_sampling_run(
            SamplingRunRecord(
                run_id=persistence.run_id,
                village_name=result.village_name,
                village_id=result.village_id,
                island_id=result.island_id,
                frame_size=result.frame_size,
                target_completed_participants=result.target_completed_participants,
                seed=seed,
                primary_household_ids=result.primary_household_ids,
                reserve_household_ids=result.reserve_household_ids,
            )
        )

        for sampled in result.processed_households:
            persistence.persist_processed_household(
                ProcessedHouseholdRecord(
                    run_id=persistence.run_id,
                    village_name=result.village_name,
                    village_id=result.village_id,
                    island_id=result.island_id,
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

        analysis_rows = []
        for participant_result in result.collected_participant_results:
            persistence.persist_participant_collection(participant_result)

            normalized = normalization.normalize_participant(participant_result)
            persistence.persist_normalized_participant(normalized)

            analysis_row = derivation.derive_analysis_row(normalized)
            persistence.append_analysis_row_jsonl(analysis_row)
            analysis_rows.append(analysis_row)

        persistence.write_analysis_rows_csv(analysis_rows)
        progress.stop()

    _render_village_save_summary(persistence.output_dir)


@app.command("collect-study-default-village-and-save")
def collect_study_default_village_and_save(
    village_name: str = typer.Option(..., help="Village name to collect from."),
    n: int = typer.Option(..., help="Target completed participants."),
    reserve_n: int = typer.Option(20, help="Number of reserve households to pre-generate."),
    seed: int = typer.Option(401, help="Seed for reproducible random sampling."),
    min_age: int = typer.Option(21, help="Minimum age for adult eligibility."),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
    run_id: str | None = typer.Option(
        None,
        help="Optional run id. If omitted, a new run directory is created.",
    ),
) -> None:
    """Run the full village workflow with study defaults and save run-scoped outputs."""
    ensure_auth_or_exit()

    collection_plan = _build_study_default_collection_plan(include_timeline=include_timeline)

    sampling_plan = SamplingPlan(
        households_per_village=n,
        reserve_households_per_village=reserve_n,
        adults_only_min_age=min_age,
        seed=seed,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        sampling = SamplingService(collector)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()
        derivation = DerivationService(PLACE_TO_ISLAND)
        workflow = CollectionWorkflow(
            collector=collector,
            sampling=sampling,
            data_collection=data_collection,
            normalization=normalization,
            derivation=derivation,
            progress=progress,
        )

        resolved_run_id = run_id or _build_village_run_id(
            village_name=village_name,
            n=n,
            seed=seed,
        )

        persistence = PersistenceService(
            data_dir=config.settings.data_dir,
            run_id=resolved_run_id,
            save_debug_payloads=config.settings.save_debug_payloads,
        )

        village = collector.fetch_village(village_name)
        result = workflow.collect_village(
            village=village,
            sampling_plan=sampling_plan,
            collection_plan=collection_plan,
        )

        from scraper.models.analysis import ProcessedHouseholdRecord, SamplingRunRecord

        persistence.persist_sampling_run(
            SamplingRunRecord(
                run_id=persistence.run_id,
                village_name=result.village_name,
                village_id=result.village_id,
                island_id=result.island_id,
                frame_size=result.frame_size,
                target_completed_participants=result.target_completed_participants,
                seed=seed,
                primary_household_ids=result.primary_household_ids,
                reserve_household_ids=result.reserve_household_ids,
            )
        )

        for sampled in result.processed_households:
            persistence.persist_processed_household(
                ProcessedHouseholdRecord(
                    run_id=persistence.run_id,
                    village_name=result.village_name,
                    village_id=result.village_id,
                    island_id=result.island_id,
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

        analysis_rows = []
        for participant_result in result.collected_participant_results:
            persistence.persist_participant_collection(participant_result)

            normalized = normalization.normalize_participant(participant_result)
            persistence.persist_normalized_participant(normalized)

            analysis_row = derivation.derive_analysis_row(normalized)
            persistence.append_analysis_row_jsonl(analysis_row)
            analysis_rows.append(analysis_row)

        persistence.write_analysis_rows_csv(analysis_rows)
        progress.stop()

    _render_village_save_summary(persistence.output_dir)


@app.command("collect-study-data-and-save")
def collect_study_data_and_save(
    village_name: list[str] = typer.Option(
        ...,
        help="Village name to include. Repeat this option for multiple villages.",
    ),
    n: int = typer.Option(..., help="Target completed participants per village."),
    reserve_n: int = typer.Option(20, help="Number of reserve households to pre-generate per village."),
    seed: int = typer.Option(401, help="Seed for reproducible random sampling."),
    min_age: int = typer.Option(21, help="Minimum age for adult eligibility."),
    summary_field: list[str] = typer.Option(
        [],
        help="Summary field source names to collect. Repeat this option for multiple fields.",
    ),
    question: list[str] = typer.Option(
        [],
        help='Chat question specs in the form key="Question text". Repeat for multiple questions.',
    ),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
    run_id: str | None = typer.Option(
        None,
        help="Optional study run id. If omitted, a new study run directory is created.",
    ),
) -> None:
    """Run the full configurable workflow across multiple listed villages and save one study run."""
    ensure_auth_or_exit()

    if not village_name:
        raise typer.BadParameter("At least one --village-name must be provided.")

    collection_plan = _build_collection_plan(
        summary_field=summary_field,
        question=question,
        include_timeline=include_timeline,
    )
    question_specs = list(question)

    sampling_plan = SamplingPlan(
        households_per_village=n,
        reserve_households_per_village=reserve_n,
        adults_only_min_age=min_age,
        seed=seed,
    )

    resolved_study_run_id = run_id or _build_study_run_id(
        village_names=village_name,
        n=n,
        seed=seed,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        sampling = SamplingService(collector)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()
        derivation = DerivationService(PLACE_TO_ISLAND)
        workflow = CollectionWorkflow(
            collector=collector,
            sampling=sampling,
            data_collection=data_collection,
            normalization=normalization,
            derivation=derivation,
            progress=progress,
        )

        persistence = PersistenceService(
            data_dir=config.settings.data_dir,
            run_id=resolved_study_run_id,
            save_debug_payloads=config.settings.save_debug_payloads,
        )

        all_analysis_rows = workflow.collect_study(
            village_names=village_name,
            sampling_plan=sampling_plan,
            collection_plan=collection_plan,
            persistence=persistence,
            question_specs=question_specs,
        )
        progress.stop()

    _render_study_save_summary(persistence.output_dir, len(village_name), len(all_analysis_rows))


@app.command("collect-study-default-data-and-save")
def collect_study_default_data_and_save(
    village_name: list[str] = typer.Option(
        ...,
        help="Village name to include. Repeat this option for multiple villages.",
    ),
    n: int = typer.Option(..., help="Target completed participants per village."),
    reserve_n: int = typer.Option(20, help="Number of reserve households to pre-generate per village."),
    seed: int = typer.Option(401, help="Seed for reproducible random sampling."),
    min_age: int = typer.Option(21, help="Minimum age for adult eligibility."),
    include_timeline: bool = typer.Option(True, help="Include raw timeline events."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
    run_id: str | None = typer.Option(
        None,
        help="Optional study run id. If omitted, a new study run directory is created.",
    ),
) -> None:
    """
    Run the full multi-village workflow using the current study defaults and save one study run.

    Current defaults:
    - summary fields: age, current_residence, money_summary, occupation_summary
    - chat questions: birth_village, income
    """
    ensure_auth_or_exit()

    if not village_name:
        raise typer.BadParameter("At least one --village-name must be provided.")

    collection_plan = _build_study_default_collection_plan(include_timeline=include_timeline)
    question_specs = list(STUDY_DEFAULT_QUESTION_SPECS)

    sampling_plan = SamplingPlan(
        households_per_village=n,
        reserve_households_per_village=reserve_n,
        adults_only_min_age=min_age,
        seed=seed,
    )

    resolved_study_run_id = run_id or _build_study_run_id(
        village_names=village_name,
        n=n,
        seed=seed,
    )

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        sampling = SamplingService(collector)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()
        derivation = DerivationService(PLACE_TO_ISLAND)
        workflow = CollectionWorkflow(
            collector=collector,
            sampling=sampling,
            data_collection=data_collection,
            normalization=normalization,
            derivation=derivation,
            progress=progress,
        )

        persistence = PersistenceService(
            data_dir=config.settings.data_dir,
            run_id=resolved_study_run_id,
            save_debug_payloads=config.settings.save_debug_payloads,
        )

        all_analysis_rows = workflow.collect_study(
            village_names=village_name,
            sampling_plan=sampling_plan,
            collection_plan=collection_plan,
            persistence=persistence,
            question_specs=question_specs,
        )
        progress.stop()

    _render_study_save_summary(persistence.output_dir, len(village_name), len(all_analysis_rows))


@app.command("resume-study-run")
def resume_study_run(
    run_id: str = typer.Option(..., help="Existing study run id under data/runs/."),
    progress_level: int = typer.Option(1, help="Progress detail level: 0, 1, or 2."),
) -> None:
    """
    Resume an interrupted study run from its checkpoint file.

    The run must already exist under:
        data/runs/<RUN_ID>/
    and contain:
        state/run_state.json
    """
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        sampling = SamplingService(collector)
        progress = ConsoleProgressReporter(max_level=progress_level)
        data_collection = DataCollectionService(
            collector=collector,
            progress=progress,
        )
        normalization = NormalizationService()
        derivation = DerivationService(PLACE_TO_ISLAND)
        workflow = CollectionWorkflow(
            collector=collector,
            sampling=sampling,
            data_collection=data_collection,
            normalization=normalization,
            derivation=derivation,
            progress=progress,
        )

        persistence = PersistenceService(
            data_dir=config.settings.data_dir,
            run_id=run_id,
            save_debug_payloads=config.settings.save_debug_payloads,
        )

        all_analysis_rows = workflow.resume_study(
            persistence=persistence,
        )
        progress.stop()

    _render_resume_summary(persistence.output_dir, len(all_analysis_rows))


if __name__ == "__main__":
    app()
