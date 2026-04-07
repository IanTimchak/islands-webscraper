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
- [x] `IslandsSession.from_config()`
- [ ] `IslandsSession.from_cookie_header(base_url, cookie_header)` if we want to support raw cookie header in config (vs just parsing it in config)
- [x] Basic timeout and pacing config
- [ ] Retry policy if not yet actually wired in

## C. `models/pages.py`

- [x] `VillagePage`
- [x] `HouseholdPage`
- [x] `Resident`
- [x] `IslanderPage`
- [x] `ChatResponse`
- [x] `ConsentResponse`

## D. `parsers/village.py`

- [x] Parse village id and island id from HTML
- [x] Parse house id list from HTML
- [x] Return `VillagePage`

## E. `services/collection.py`

- [x] `Collector` class wiring session + parsers
- [x] `fetch_village(village_name: str) -> VillagePage`
