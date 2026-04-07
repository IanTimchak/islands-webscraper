# Architecture

This document describes the layout and layer responsibilities of `islands-webscraper`.

---

## Repository Structure

```
islands-webscraper/
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── docs/
│   ├── api.md
│   └── architecture.md
├── src/
│   └── islands_webscraper/
│       ├── __init__.py
│       ├── config.py
│       ├── exceptions.py
│       ├── utils.py
│       ├── client/
│       │   ├── __init__.py
│       │   ├── session.py
│       │   └── endpoints.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── pages.py
│       │   ├── normalized.py
│       │   └── analysis.py
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── village.py
│       │   ├── house.py
│       │   ├── islander.py
│       │   ├── chat.py
│       │   └── consent.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── collection.py
│       │   ├── sampling.py
│       │   ├── normalization.py
│       │   └── derivation.py
│       └── cli/
│           ├── __init__.py
│           └── main.py
├── tests/
│   ├── fixtures/
│   │   ├── village_vardo.html
│   │   ├── house_v0_h5.html
│   │   ├── islander_example.html
│   │   ├── consent_accept.txt
│   │   └── chat_birth_village.txt
│   ├── test_village_parser.py
│   ├── test_house_parser.py
│   ├── test_islander_parser.py
│   ├── test_chat_parser.py
│   └── test_sampling.py
└── data/
    ├── raw/
    ├── normalized/
    └── analysis/
```

---

## Code Flow

```
client          →   fetch raw HTML/text payloads
parsers         →   turn payloads into typed page objects
services/collection     →   drive the fetch + parse workflow
services/sampling       →   village, household, and adult sampling
services/normalization  →   build intermediate normalized records
services/derivation     →   build final analysis rows
cli             →   expose user commands
```

---

## Layer Responsibilities

### `client/`

Handles authenticated HTTP communication. This layer is intentionally dumb — no parsing logic lives here.

**`session.py`** — `IslandsSession`

- constructs and holds the authenticated session from environment or explicit cookie header
- applies timeouts, retries, and rate limiting via the transport

**`endpoints.py`** — URL path builders only

```python
def village_page(village_name: str) -> str: ...
def house_page(village_id: int, house_id: int) -> str: ...
def islander_page(islander_id: str) -> str: ...
def consent(islander_id: str) -> str: ...
def chat(chatid: str, message: str) -> str: ...
```

---

### `models/`

Typed Pydantic models for every data stage. No parsing or business logic lives here.

**`pages.py`** — raw-ish parsed page models

- `VillagePage`
- `HouseholdPage`, `Resident`
- `IslanderPage`
- `ChatResponse`
- `ConsentResponse`

**`normalized.py`** — intermediate structured records

- `NormalizedIslander`

**`analysis.py`** — final minimal dataset rows

- `AnalysisRow`

> If raw acquisition records grow richer over time, a `raw.py` model file may be worth adding to hold `RawIslanderRecord` and `RawChatAttempt` separately from page models.

---

### `parsers/`

One parser file per response type. No cross-endpoint logic.

| Module        | Parses                                    |
| ------------- | ----------------------------------------- |
| `village.py`  | Village page HTML → `VillagePage`         |
| `house.py`    | Household page HTML → `HouseholdPage`     |
| `islander.py` | Islander page HTML → `IslanderPage`       |
| `chat.py`     | Chat response text → `ChatResponse`       |
| `consent.py`  | Consent response text → `ConsentResponse` |

This scoping makes parsers easy to test, debug, and update independently if the site changes.

---

### `services/`

This is where the study design lives. All real project logic belongs here.

| Module             | Responsibility                                                  |
| ------------------ | --------------------------------------------------------------- |
| `collection.py`    | `Collector` — orchestrates fetch + parse for each endpoint      |
| `sampling.py`      | `HouseholdSampler` — reproducible household and adult selection |
| `normalization.py` | `Normalizer` — raw page models → `NormalizedIslander`           |
| `derivation.py`    | `Deriver` — `NormalizedIslander` → `AnalysisRow`                |

---

### `cli/`

Thin entry point. Calls services directly — no pipeline logic here.

```bash
islands inspect village <VILLAGE_NAME>
islands inspect house --village-id <ID> --house-id <ID>
islands inspect islander <ISLANDER_ID>
islands collect raw --villages ... --per-village 40
islands build normalized
islands build analysis
```

---

### `utils.py`

Shared helpers with no domain logic. Kept as a single file for now.

If it grows, split later into `text.py`, `files.py`, and `rate_limit.py` — but that is not needed up front.

---

### `config.py` / `exceptions.py`

Both worth having from the start.

**`config.py`** — loads and validates environment variables (`ISLANDS_BASE_URL`, `ISLANDS_COOKIE_HEADER`)

**`exceptions.py`** — project-wide error types

- `AuthenticationError`
- `RateLimitError`
- `ParseError`
- `ConsentError`
- `ChatUnavailableError`

---

### `tests/`

Parser and sampling unit tests backed by fixture files captured from the live simulator. Kept outside `src/`.

---

### `data/`

Runtime output directory, not committed to version control.

```
data/
  raw/          # RawIslanderRecord JSON files
  normalized/   # NormalizedIslander JSON files
  analysis/     # AnalysisRow CSV or JSON
```

---

## Design Principles

- **Raw payload preservation** — raw HTML and text are retained on model objects so parsing failures are recoverable without re-fetching
- **Typed models throughout** — every stage boundary uses Pydantic models, not dicts
- **Conservative transport** — sequential requests with configurable delays, jitter, and retries
- **Clear layer separation** — fetching, parsing, and recoding are distinct concerns with no cross-layer leakage
- **Reproducible sampling** — all random selection points accept an optional seed
- **Thin CLI** — the CLI calls services directly; no pipeline layer needed at this scale
