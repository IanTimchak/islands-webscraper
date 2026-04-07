from __future__ import annotations

import typer

from scraper import config
from scraper.auth_env import clear_auth_cookie, get_auth_cookie, set_auth_cookie
from scraper.auth_browser import (
    SUPPORTED_BROWSERS,
    build_cookie_header_for_domain,
    open_login_page,
)
from scraper.client.session import IslandsSession
from scraper.services.auth import require_auth_present_and_fresh, validate_current_auth
from scraper.services.collection import Collector

app = typer.Typer(help="Islands webscraper CLI")


@app.callback()
def main() -> None:
    # root CLI group
    pass


@app.command()
def hello() -> None:
    # quick sanity check that the CLI is wired up
    print("islands-webscraper is set up")


@app.command()
def fetch_village(village_name: str) -> None:
    # cheap local guard only
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)
        village = collector.fetch_village(village_name)

    typer.echo(f"Village: {village.village_name}")
    typer.echo(f"Village ID: {village.village_id}")
    typer.echo(f"Island ID: {village.island_id}")
    typer.echo(f"Households found: {len(village.house_ids)}")


@app.command("consent")
def consent(
    village_name: str = typer.Option(..., help="Village name where the islander was found"),
    islander_id: str = typer.Option(..., help="Islander id"),
) -> None:
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)

        # fetch village context first
        village = collector.fetch_village(village_name)

        # fetch the islander page so consent request uses proper context
        islander = collector.fetch_islander(village=village, islander_id=islander_id)

        # send consent request
        consent_response = collector.request_consent(islander)

    typer.echo(f"Islander ID: {consent_response.islander_id}")
    typer.echo(f"Outcome: {consent_response.outcome}")
    typer.echo(f"Timestamp: {consent_response.timestamp_text}")
    typer.echo(f"Message: {consent_response.message}")


@app.command("ask")
def ask(
    village_name: str = typer.Option(..., help="Village name where the islander was found"),
    islander_id: str = typer.Option(..., help="Islander id"),
    question: str = typer.Option(..., help="Question to ask"),
) -> None:
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)

        # get village context first
        village = collector.fetch_village(village_name)

        # get islander page so we have the chatid
        islander = collector.fetch_islander(village=village, islander_id=islander_id)

        # ask the question through alice.php
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


@app.command("fetch-islander")
def fetch_islander(
    village_name: str = typer.Option(..., help="Village name where the islander was found"),
    islander_id: str = typer.Option(..., help="Islander id"),
) -> None:
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
        typer.echo(
            f"- age_stage={event.age_stage} | {event.date_code} | {event.text}"
        )


@app.command("fetch-household")
def fetch_household(
    village_name: str = typer.Option(..., help="Village name, e.g. Vardo"),
    house_id: int = typer.Option(..., help="Internal house id"),
) -> None:
    ensure_auth_or_exit()

    with IslandsSession.from_config() as session:
        collector = Collector(session)

        # get the village object first so household fetch uses the full context
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


@app.command("auth-login")
def auth_login(
    browser: str = typer.Option(..., help="Browser to use: chrome or firefox"),
    no_open: bool = typer.Option(False, help="Do not open the login page automatically"),
) -> None:
    """
    Guide the user through browser login, then import cookies into .env.
    """
    browser = browser.lower().strip()
    if browser not in SUPPORTED_BROWSERS:
        raise typer.BadParameter(
            f"Unsupported browser '{browser}'. Use one of: {sorted(SUPPORTED_BROWSERS)}"
        )

    # builds the site URL we want the user to log into
    base_url = config.settings.islands_base_url.rstrip("/")
    login_url = f"{base_url}/"

    typer.echo(f"Selected browser: {browser}")
    typer.echo(f"Site: {login_url}")

    # opens the browser for the user unless they disabled it
    if not no_open:
        typer.echo("Opening login page in your browser...")
        open_login_page(login_url, browser)

    typer.echo("")
    typer.echo("Please log in fully in that browser window.")
    typer.echo("After login is complete, return here and press Enter.")
    input()

    typer.echo("Importing cookies from browser profile...")

    # gets cookie data from the selected browser
    try:
        cookie_header = build_cookie_header_for_domain(browser=browser, base_url=base_url)
    except Exception as exc:
        typer.echo(f"Cookie import failed: {exc}")
        typer.echo("Fallback: run 'islands auth-set-cookie' and paste the Cookie header manually.")
        raise typer.Exit(code=1)

    # stores the cookie in .env with a timestamp
    set_auth_cookie(cookie_header)

    # one live validation here is worth it because we just captured auth
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
    """
    typer.echo("Paste the authenticated Cookie header value.")
    typer.echo("Example: PHPSESSID=...; other_cookie=...")
    cookie_header = typer.prompt("Cookie header", hide_input=False).strip()

    if not cookie_header:
        typer.echo("No cookie header provided.")
        raise typer.Exit(code=1)

    # saves the manually supplied cookie
    set_auth_cookie(cookie_header)

    # validates once here so we do not save junk auth silently
    typer.echo("Stored auth in .env. Validating session...")
    status = validate_current_auth()

    if status.is_valid:
        typer.echo(f"Success: {status.message}")
        return

    typer.echo(f"Validation failed: {status.message}")
    raise typer.Exit(code=1)


@app.command("auth-test")
def auth_test() -> None:
    """
    Test whether the current .env auth is valid.
    """
    # makes sure something is actually stored first
    cookie = get_auth_cookie()
    if not cookie:
        typer.echo("No ISLANDS_COOKIE_HEADER found in .env.")
        raise typer.Exit(code=1)

    # explicit live check on demand
    status = validate_current_auth()
    if status.is_valid:
        typer.echo(f"Valid: {status.message}")
        return

    typer.echo(f"Invalid: {status.message}")
    raise typer.Exit(code=1)


@app.command("auth-clear")
def auth_clear() -> None:
    """
    Remove stored auth values from .env.
    """
    # clears the saved cookie and timestamp
    clear_auth_cookie()
    typer.echo("Cleared Islands auth values from .env.")



# helpers
def ensure_auth_or_exit() -> None:
    try:
        require_auth_present_and_fresh()
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()