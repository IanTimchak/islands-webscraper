# Todo

Initial setup expansion — get the fetch/parse loop working for a single village end-to-end.

---

## A. `client/endpoints.py`

- [x] `village_page(village_name: str) -> str`
- [x] `house_page(village_id: int, house_id: int) -> str`
- [x] `islander_page(islander_id: str) -> str`
- [x] `consent(islander_id: str) -> str`
- [x] `chat(chatid: str, message: str) -> str`
- [ ] `task(islander_id: str, code: str) -> str`
- [ ] `contact(islander_id: str) -> str`

## B. `client/session.py`

- [x] Authenticated `httpx.Client` wrapper
- [x] `IslandsSession.from_config()`
- [ ] `IslandsSession.from_cookie_header(base_url, cookie_header)` if we want explicit raw-cookie construction
- [x] Basic timeout and pacing config
- [ ] Retry policy if not yet actually wired in
- [ ] Centralized detection/handling for obvious unauthenticated responses

## C. `models/pages.py`

- [x] `VillagePage`
- [x] `HouseholdPage`
- [x] `Resident`
- [x] `IslanderPage`
- [x] `ChatResponse`
- [x] `ConsentResponse`
- [ ] Expand `IslanderPage` with:
  - [ ] `summary_lines`
  - [ ] `current_residence`
  - [ ] `age`
  - [ ] `income_summary`
  - [ ] `occupation_summary`
  - [ ] `timeline_events`
  - [ ] `chatid`
  - [ ] `awake`

## D. `parsers/village.py`

- [x] Parse village id and island id from HTML
- [x] Parse house id list from HTML
- [x] Return `VillagePage`

## E. `services/collection.py`

- [x] `Collector` class wiring session + parsers
- [x] `fetch_village(village_name: str) -> VillagePage`
- [ ] `fetch_household(village_id: int, house_id: int) -> HouseholdPage`
- [ ] `fetch_islander(islander_id: str) -> IslanderPage`
- [ ] `request_consent(islander_id: str) -> ConsentResponse`
- [ ] `ask(chatid: str, question: str) -> ChatResponse`

---

# Next vertical slice — household pages

## F. `parsers/house.py`

- [x] Parse house title / house id from HTML
- [x] Parse resident rows
- [x] Parse resident name
- [x] Parse resident age
- [x] Parse resident `islander_id`
- [x] Return `HouseholdPage`
- [x] Preserve both requested internal house id and displayed house number

## G. CLI additions

- [x] `fetch-household --village-id <id> --house-id <id>`
- [x] Print resident count and resident list
- [x] Confirm ages and islander ids parse correctly

## G. Household fetch architecture

- [x] `Collector.fetch_household(village: VillagePage, house_id: int)`
- [x] Use `VillagePage` context instead of loose `village_id` / `village_name`

---

# Next vertical slice — islander pages

## H. `parsers/islander.py`

- [ ] Parse islander id from script/page
- [ ] Parse displayed name
- [ ] Parse `chatid`
- [ ] Parse `awake`
- [ ] Parse summary lines
- [ ] Parse current residence
- [ ] Parse age
- [ ] Parse income summary
- [ ] Parse occupation summary
- [ ] Parse timeline events
- [ ] Return `IslanderPage`

## I. CLI additions

- [ ] `fetch-islander <islander_id>`
- [ ] Print name, chatid, awake status
- [ ] Print summary lines
- [ ] Print first few timeline events

---

# Chat / consent slice

## J. `parsers/chat.py`

- [ ] Parse raw `alice.php` response
- [ ] Extract plain response text
- [ ] Extract `key=value` updates
- [ ] Return `ChatResponse`

## K. `parsers/consent.py`

- [ ] Parse semicolon-delimited consent response
- [ ] Return `ConsentResponse`

## L. CLI additions

- [ ] `auth-test` remains manual validation
- [ ] `ask <islander_id> "<question>"` helper command
- [ ] `consent <islander_id>` helper command

---

# Sampling layer

## M. `services/sampling.py`

- [ ] Randomly sample household ids from a village
- [ ] Generate reserve list
- [ ] Filter eligible adults (`age >= 21`)
- [ ] Randomly choose one eligible adult
- [ ] Deterministic seed support

## N. CLI additions

- [ ] `sample-village <village_name> --n 5 --seed 123`
- [ ] Print chosen household ids
- [ ] Optionally print chosen eligible adult per sampled household

---

# Normalization layer

## O. `models/normalized.py`

- [ ] `NormalizedIslander`
- [ ] `AnalysisRow`

## P. `services/normalization.py`

- [ ] Extract birth village
- [ ] Extract current village
- [ ] Parse numeric income
- [ ] Gather education events
- [ ] Gather occupation evidence

## Q. `services/derivation.py`

- [ ] Derive `immigrant_other_island`
- [ ] Derive `education_level`
- [ ] Derive `occupation_group`
- [ ] Build final analysis row

---

# Tests / fixtures

## R. `tests/fixtures/`

- [ ] Save one known village HTML
- [ ] Save one known house HTML
- [ ] Save one known islander HTML
- [ ] Save one known chat response
- [ ] Save one known consent response

## S. Parser tests

- [ ] `test_village_parser.py`
- [ ] `test_house_parser.py`
- [ ] `test_islander_parser.py`
- [ ] `test_chat_parser.py`
- [ ] `test_consent_parser.py`
