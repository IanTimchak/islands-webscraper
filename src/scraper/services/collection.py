from __future__ import annotations

from scraper.client.session import IslandsSession
from scraper.models.pages import ChatResponse, ConsentResponse, HouseholdPage, IslanderPage, VillagePage
from scraper.parsers.consent import parse_consent_response
from scraper.parsers.chat import parse_chat_response
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
    
    def ask(self, islander: IslanderPage, question: str) -> ChatResponse:
        # need the chat session id to ask anything
        if not islander.chatid:
            raise ValueError(f"No chatid available for islander {islander.islander_id}.")

        raw_text = self.session.get_chat_text(
            chatid=islander.chatid,
            message=question,
            islander_id=islander.islander_id,
        )

        return parse_chat_response(
            raw_text=raw_text,
            chatid=islander.chatid,
            question=question,
        )
    
    def request_consent(self, islander: IslanderPage) -> ConsentResponse:
        # gets raw consent response from the site
        raw_text = self.session.get_consent_text(islander_id=islander.islander_id)

        # parses it into a structured consent object
        return parse_consent_response(
            raw_text=raw_text,
            islander_id=islander.islander_id,
        )