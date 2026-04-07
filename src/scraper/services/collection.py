from __future__ import annotations

from scraper.client.session import IslandsSession
from scraper.models.pages import HouseholdPage, IslanderPage, VillagePage
from scraper.parsers.islander import parse_islander_page
from scraper.parsers.house import parse_household_page
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

    def fetch_household(self, village: VillagePage, house_id: int) -> HouseholdPage:
        # gets raw household HTML using village context
        html = self.session.get_house_html(
            village_id=village.village_id,
            house_id=house_id,
            village_name=village.village_name,
        )

        # parses it into a structured household object
        return parse_household_page(html, village_id=village.village_id, requested_house_id=house_id)
    
    def fetch_islander(self, village: VillagePage, islander_id: str) -> IslanderPage:
        # gets raw islander HTML using village context
        html = self.session.get_islander_html(
            islander_id=islander_id,
            village_name=village.village_name,
        )

        # parses it into a structured islander object
        return parse_islander_page(html)