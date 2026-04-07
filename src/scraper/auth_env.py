from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


ENV_PATH = Path(".env")
AUTH_MAX_AGE_HOURS = 20


def utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def load_env_file(path: Path = ENV_PATH) -> dict[str, str]:
    """Load key-value pairs from a .env file."""
    if not path.exists():
        return {}

    raw = dotenv_values(path)
    out: dict[str, str] = {}

    for key, value in raw.items():
        if key is None:
            continue
        out[key] = "" if value is None else str(value)

    return out


def save_env_file(values: dict[str, str], path: Path = ENV_PATH) -> None:
    """Persist key-value pairs to a .env file."""
    lines: list[str] = []

    for key in sorted(values):
        value = values[key]
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key}="{escaped}"')

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    load_dotenv(path, override=True)


def set_auth_cookie(cookie_header: str, path: Path = ENV_PATH) -> None:
    """Store the Islands auth cookie and capture timestamp in .env."""
    values = load_env_file(path)
    values["ISLANDS_COOKIE_HEADER"] = cookie_header.strip()
    values["ISLANDS_AUTH_CAPTURED_AT"] = utc_now_iso()
    save_env_file(values, path)


def get_auth_cookie(path: Path = ENV_PATH) -> str:
    """Read the stored Islands auth cookie from .env."""
    values = load_env_file(path)
    return values.get("ISLANDS_COOKIE_HEADER", "").strip()


def get_auth_captured_at(path: Path = ENV_PATH) -> str:
    """Read the stored auth capture timestamp from .env."""
    values = load_env_file(path)
    return values.get("ISLANDS_AUTH_CAPTURED_AT", "").strip()


def clear_auth_cookie(path: Path = ENV_PATH) -> None:
    """Remove stored Islands auth values from .env."""
    values = load_env_file(path)
    values.pop("ISLANDS_COOKIE_HEADER", None)
    values.pop("ISLANDS_AUTH_CAPTURED_AT", None)
    save_env_file(values, path)


def parse_auth_timestamp(timestamp: str) -> datetime | None:
    """Parse an ISO auth timestamp into UTC."""
    if not timestamp.strip():
        return None

    try:
        dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def auth_age(path: Path = ENV_PATH) -> timedelta | None:
    """Return the age of the stored auth cookie."""
    captured = parse_auth_timestamp(get_auth_captured_at(path))
    if captured is None:
        return None

    return datetime.now(timezone.utc) - captured


def auth_is_stale(
    max_age_hours: int = AUTH_MAX_AGE_HOURS,
    path: Path = ENV_PATH,
) -> bool:
    """Return True if the stored auth is missing a timestamp or is too old."""
    age = auth_age(path)
    if age is None:
        return True

    return age > timedelta(hours=max_age_hours)