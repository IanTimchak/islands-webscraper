# Todo

Initial setup expansion — get the fetch/parse loop working for a single village end-to-end.

---

## A. `client/endpoints.py`

- [x] `village_page(village_name: str) -> str`
- [x] `house_page(village_id: int, house_id: int) -> str`
- [x] `islander_page(islander_id: str) -> str`
- [x] `consent(islander_id: str) -> str`
- [x] `chat(chatid: str, message: str) -> str`

## B. `client/session.py`

- [x] Authenticated `httpx.Client` wrapper
- [x] `IslandsSession.from_env()`
- [x] `IslandsSession.from_cookie_header(base_url, cookie_header)`
- [x] Basic timeout and retry config

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
