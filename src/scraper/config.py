from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    islands_base_url: str = os.getenv("ISLANDS_BASE_URL", "https://islands.smp.uq.edu.au")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    request_base_delay_seconds: float = float(os.getenv("REQUEST_BASE_DELAY_SECONDS", "1.2"))
    request_jitter_min_seconds: float = float(os.getenv("REQUEST_JITTER_MIN_SECONDS", "0.4"))
    request_jitter_max_seconds: float = float(os.getenv("REQUEST_JITTER_MAX_SECONDS", "1.0"))


def get_cookie_header() -> str:
    load_dotenv(override=True)
    return os.getenv("ISLANDS_COOKIE_HEADER", "").strip()


settings = Settings()