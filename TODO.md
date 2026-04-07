# Todo

Initial setup expansion — get the fetch/parse loop working for a single village end-to-end.

---

## A. `client/endpoints.py`

- [ ] `village_page(village_name: str) -> str`
- [ ] `house_page(village_id: int, house_id: int) -> str`
- [ ] `islander_page(islander_id: str) -> str`
- [ ] `consent(islander_id: str) -> str`
- [ ] `chat(chatid: str, message: str) -> str`

## B. `client/session.py`

- [ ] Authenticated `httpx.Client` wrapper
- [ ] `IslandsSession.from_env()`
- [ ] `IslandsSession.from_cookie_header(base_url, cookie_header)`
- [ ] Basic timeout and retry config

## C. `models/pages.py`

- [ ] `VillagePage`
- [ ] `HouseholdPage`
- [ ] `Resident`
- [ ] `IslanderPage`
- [ ] `ChatResponse`
- [ ] `ConsentResponse`

## D. `parsers/village.py`

- [ ] Parse village id and island id from HTML
- [ ] Parse house id list from HTML
- [ ] Return `VillagePage`

## E. `services/collection.py`

- [ ] `Collector` class wiring session + parsers
- [ ] `fetch_village(village_name: str) -> VillagePage`
