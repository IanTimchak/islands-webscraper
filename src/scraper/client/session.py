from __future__ import annotations

import random
import time
from dataclasses import dataclass

import httpx

from scraper import config
from scraper.client import endpoints


@dataclass(slots=True)
class RequestTiming:
    """Configuration for polite request pacing."""

    base_delay_seconds: float = 1.2
    jitter_min_seconds: float = 0.4
    jitter_max_seconds: float = 1.0

    def next_delay(self) -> float:
        """Return the next delay duration."""
        return self.base_delay_seconds + random.uniform(
            self.jitter_min_seconds,
            self.jitter_max_seconds,
        )


class IslandsSession:
    """
    Thin authenticated HTTP client for the Islands simulator.

    This class is responsible only for:
    - session/cookie setup
    - request execution
    - polite pacing
    - returning raw response text
    """

    def __init__(
        self,
        base_url: str,
        cookie_header: str,
        timeout_seconds: float = 30.0,
        timing: RequestTiming | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.cookie_header = cookie_header
        self.timeout_seconds = timeout_seconds
        self.timing = timing or RequestTiming()

        headers = {
            "Cookie": self.cookie_header,
            "User-Agent": "islands-webscraper/0.1.0",
        }

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        )

    @classmethod
    def from_config(cls) -> "IslandsSession":
        return cls(
            base_url=config.settings.islands_base_url,
            cookie_header=config.get_cookie_header(),
            timeout_seconds=config.settings.request_timeout_seconds,
            timing=RequestTiming(
                base_delay_seconds=config.settings.request_base_delay_seconds,
                jitter_min_seconds=config.settings.request_jitter_min_seconds,
                jitter_max_seconds=config.settings.request_jitter_max_seconds,
            ),
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "IslandsSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _sleep(self) -> None:
        """Sleep for a polite, jittered interval before a request."""
        time.sleep(self.timing.next_delay())

    def _get_text(self, path: str, extra_headers: dict[str, str] | None = None) -> str:
        # polite delay before request
        self._sleep()

        headers = extra_headers or {}
        response = self._client.get(path, headers=headers)

        response.raise_for_status()
        return response.text

    def get_village_html(self, village_name: str) -> str:
        """Fetch a village page as raw HTML."""
        return self._get_text(endpoints.village_page(village_name))

    def get_house_html(self, village_id: int, house_id: int, village_name: str) -> str:
        # this endpoint seems to want to look like an XHR from the village page
        headers = {
            "Accept": "*/*",
            "Referer": f"{self.base_url}village.php?{village_name}",
            "X-Requested-With": "XMLHttpRequest",
        }
        return self._get_text(
            endpoints.house_page(village_id, house_id),
            extra_headers=headers,
        )

    def get_islander_html(self, islander_id: str) -> str:
        """Fetch an islander page as raw HTML."""
        return self._get_text(endpoints.islander_page(islander_id))

    def get_consent_text(self, islander_id: str) -> str:
        """Fetch a consent response as raw text."""
        return self._get_text(endpoints.consent(islander_id))

    def get_chat_text(self, chatid: str, message: str) -> str:
        """Fetch a direct chat response as raw text."""
        return self._get_text(endpoints.chat(chatid, message))

    def get_task_text(self, islander_id: str, code: str) -> str:
        """Fetch a task response as raw text."""
        return self._get_text(endpoints.task(islander_id, code))

    def get_contact_text(self, islander_id: str) -> str:
        """Fetch a contact-toggle response as raw text."""
        return self._get_text(endpoints.contact(islander_id))