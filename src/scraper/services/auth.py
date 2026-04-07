from __future__ import annotations

from dataclasses import dataclass

from scraper.auth_env import AUTH_MAX_AGE_HOURS, auth_age, auth_is_stale, get_auth_cookie
from scraper.client.session import IslandsSession


@dataclass(slots=True)
class AuthStatus:
    is_valid: bool
    message: str


def require_auth_present_and_fresh() -> None:
    """
    Cheap local auth guard.

    Checks only:
    - cookie exists
    - timestamp exists and is not stale

    Does not make any network request.
    """
    cookie = get_auth_cookie()
    if not cookie:
        raise RuntimeError(
            "No stored auth found. Run 'islands auth-login --browser firefox' "
            "or 'islands auth-login --browser chrome'."
        )

    if auth_is_stale():
        age = auth_age()
        age_text = "unknown age" if age is None else str(age).split(".")[0]
        raise RuntimeError(
            f"Stored auth is stale ({age_text}, max {AUTH_MAX_AGE_HOURS}h). "
            "Please log in again with 'islands auth-login --browser firefox' "
            "or 'islands auth-login --browser chrome'."
        )


def validate_current_auth() -> AuthStatus:
    """
    Explicit live validation.

    Use this:
    - after auth-login
    - after auth-set-cookie
    - optionally before a long collection run
    """
    try:
        with IslandsSession.from_config() as session:
            html = session.get_village_html("Vardo")
    except Exception as exc:
        return AuthStatus(False, f"request failed: {exc}")

    if response_looks_unauthenticated(html):
        return AuthStatus(False, "response appears unauthenticated")

    return AuthStatus(True, "authenticated village page detected")


def response_looks_unauthenticated(response_text: str) -> bool:
    """
    Heuristic detector for responses that look like login/unauthenticated pages.
    """
    lowered = response_text.lower()

    if "logout" in lowered and "villagemap" in lowered:
        return False

    if "login" in lowered and "logout" not in lowered:
        return True

    if "villagemap" in lowered or "mini project" in lowered:
        return False

    return False