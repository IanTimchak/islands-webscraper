from __future__ import annotations

import shutil
import subprocess
import webbrowser
from urllib.parse import urlparse

import browser_cookie3


SUPPORTED_BROWSERS = {"chrome", "firefox"}


def open_login_page(url: str, browser: str) -> None:
    """
    Open the login page in the user's selected browser if possible.
    Falls back to the default browser.
    """
    browser = browser.lower().strip()

    if browser == "chrome":
        for candidate in ("chrome", "google-chrome", "chrome.exe"):
            path = shutil.which(candidate)
            if path:
                subprocess.Popen([path, url])  # noqa: S603,S607
                return

    if browser == "firefox":
        for candidate in ("firefox", "firefox.exe"):
            path = shutil.which(candidate)
            if path:
                subprocess.Popen([path, url])  # noqa: S603,S607
                return

    webbrowser.open(url)


def _domain_matches(cookie_domain: str, target_host: str) -> bool:
    cookie_domain = cookie_domain.lstrip(".").lower()
    target_host = target_host.lower()
    return target_host == cookie_domain or target_host.endswith("." + cookie_domain)


def _load_cookie_jar(browser: str):
    browser = browser.lower().strip()

    if browser == "chrome":
        return browser_cookie3.chrome()
    if browser == "firefox":
        return browser_cookie3.firefox()

    raise ValueError(f"Unsupported browser: {browser}")


def build_cookie_header_for_domain(browser: str, base_url: str) -> str:
    """
    Import browser cookies and build a Cookie header for the target site.
    """
    jar = _load_cookie_jar(browser)
    host = urlparse(base_url).hostname
    if not host:
        raise ValueError(f"Could not determine hostname from base_url: {base_url}")

    cookie_parts: list[str] = []

    for cookie in jar:
        if _domain_matches(cookie.domain or "", host):
            cookie_parts.append(f"{cookie.name}={cookie.value}")

    if not cookie_parts:
        raise RuntimeError(
            f"No cookies found for domain '{host}' in browser '{browser}'."
        )

    return "; ".join(cookie_parts)