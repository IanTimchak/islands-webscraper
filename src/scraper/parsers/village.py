from __future__ import annotations

import ast
import re

from scraper.models.pages import VillagePage


_VILLAGE_ID_RE = re.compile(r"var\s+v\s*=\s*(\d+)\s*;")
_ISLAND_ID_RE = re.compile(r"var\s+island\s*=\s*(\d+)\s*;")
_VILLAGE_NAME_RE = re.compile(r"var\s+village\s*=\s*'([^']+)'\s*;")
_MAP_RE = re.compile(r"var\s+map\s*=\s*(\[\[.*?\]\])\s*;", re.DOTALL)


def _extract_required_int(pattern: re.Pattern[str], html: str, label: str) -> int:
    match = pattern.search(html)
    if not match:
        raise ValueError(f"Could not find {label} in village page.")
    return int(match.group(1))


def _extract_required_str(pattern: re.Pattern[str], html: str, label: str) -> str:
    match = pattern.search(html)
    if not match:
        raise ValueError(f"Could not find {label} in village page.")
    return match.group(1)


def _extract_house_ids(html: str) -> list[int]:
    match = _MAP_RE.search(html)
    if not match:
        raise ValueError("Could not find map array in village page.")

    map_literal = match.group(1)

    try:
        entries = ast.literal_eval(map_literal)
    except Exception as exc:
        raise ValueError(f"Could not parse map array: {exc}") from exc

    house_ids: list[int] = []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 2:
            continue

        maybe_house_id = entry[1]
        if isinstance(maybe_house_id, int):
            house_ids.append(maybe_house_id)

    return house_ids


def parse_village_page(html: str) -> VillagePage:
    village_id = _extract_required_int(_VILLAGE_ID_RE, html, "village id")
    island_id = _extract_required_int(_ISLAND_ID_RE, html, "island id")
    village_name = _extract_required_str(_VILLAGE_NAME_RE, html, "village name")
    house_ids = _extract_house_ids(html)

    return VillagePage(
        village_name=village_name,
        village_id=village_id,
        island_id=island_id,
        house_ids=house_ids,
        raw_html=html,
    )