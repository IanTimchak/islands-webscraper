from __future__ import annotations

from scraper.client.session import IslandsSession
from scraper.models.pages import VillagePage
from scraper.parsers.village import parse_village_page


class Collector:
    # thin orchestration layer for fetch + parse operations
    def __init__(self, session: IslandsSession) -> None:
        self.session = session

    def fetch_village(self, village_name: str) -> VillagePage:
        # gets raw HTML from the site
        html = self.session.get_village_html(village_name)

        # parses it into a structured page object
        return parse_village_page(html)