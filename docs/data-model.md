# Data Model

This document describes the typed models used across `islands-webscraper`.

---

## Page Models

These are returned by the `Collector` fetching methods and contain both parsed fields and the original raw payload.

### `VillagePage`

| Field          | Type        | Description                       |
| -------------- | ----------- | --------------------------------- |
| `village_name` | `str`       | Name as passed to the endpoint    |
| `village_id`   | `int`       | Numeric village identifier        |
| `island_id`    | `int`       | Numeric island identifier         |
| `house_ids`    | `list[int]` | All household ids in this village |
| `raw_html`     | `str`       | Original HTML payload             |

---

### `HouseholdPage`

| Field        | Type             | Description                       |
| ------------ | ---------------- | --------------------------------- |
| `village_id` | `int`            | Village this household belongs to |
| `house_id`   | `int`            | Household identifier              |
| `residents`  | `list[Resident]` | All residents listed on the page  |
| `raw_html`   | `str`            | Original HTML payload             |

---

### `Resident`

| Field         | Type  | Description                |
| ------------- | ----- | -------------------------- |
| `name`        | `str` | Full name                  |
| `age`         | `int` | Age in years               |
| `islander_id` | `str` | Unique islander identifier |

---

### `IslanderPage`

| Field               | Type        | Description                            |
| ------------------- | ----------- | -------------------------------------- |
| `islander_id`       | `str`       | Unique islander identifier             |
| `name`              | `str`       | Full name                              |
| `age`               | `int`       | Age in years                           |
| `summary_lines`     | `list[str]` | Parsed summary block lines             |
| `current_residence` | `str`       | Current village and house              |
| `chatid`            | `str`       | Chat session identifier                |
| `awake`             | `bool`      | Whether the subject is currently awake |
| `timeline_events`   | `list[...]` | Parsed life event timeline             |
| `raw_html`          | `str`       | Original HTML payload                  |

---

## Response Models

### `ConsentResponse`

| Field         | Type  | Description               |
| ------------- | ----- | ------------------------- |
| `islander_id` | `str` | Subject identifier        |
| `outcome`     | `str` | `"accept"` or `"decline"` |
| `message`     | `str` | Response message text     |
| `raw_text`    | `str` | Original response payload |

---

### `ChatResponse`

| Field           | Type   | Description                |
| --------------- | ------ | -------------------------- |
| `chatid`        | `str`  | Chat session identifier    |
| `question`      | `str`  | Question as sent           |
| `response_text` | `str`  | Subject's response         |
| `state_updates` | `dict` | Any state changes returned |
| `raw_text`      | `str`  | Original response payload  |

---

## Intermediate Models

### `RawIslanderRecord`

Persisted after fetching, before normalization. Contains the raw page and chat payloads for a single subject.

| Field              | Type                   |
| ------------------ | ---------------------- |
| `islander_page`    | `IslanderPage`         |
| `consent_response` | `ConsentResponse`      |
| `chat_attempts`    | `list[RawChatAttempt]` |

---

### `RawChatAttempt`

| Field      | Type           |
| ---------- | -------------- |
| `question` | `str`          |
| `response` | `ChatResponse` |

---

## Normalized Model

### `NormalizedIslander`

Produced by `Normalizer.normalize_islander()`. Contains structured facts extracted from raw records.

| Field                | Type            | Description                 |
| -------------------- | --------------- | --------------------------- |
| `islander_id`        | `str`           | Unique identifier           |
| `name`               | `str`           | Full name                   |
| `age`                | `int`           | Age in years                |
| `current_village`    | `str`           | Parsed current village name |
| `birth_village`      | `str \| None`   | From chat response          |
| `income_numeric`     | `float \| None` | Parsed income value         |
| `occupation_text`    | `str \| None`   | Raw occupation string       |
| `education_evidence` | `str \| None`   | Extracted education signal  |

---

## Analysis Model

### `AnalysisRow`

Produced by `Deriver.derive_analysis_row()`. Final variables used in statistical analysis.

| Field                    | Type            | Description                                |
| ------------------------ | --------------- | ------------------------------------------ |
| `islander_id`            | `str`           | Unique identifier                          |
| `immigrant_other_island` | `bool`          | Born on a different island                 |
| `income`                 | `float \| None` | Cleaned income value                       |
| `education_level`        | `str \| None`   | Derived education category                 |
| `occupation_group`       | `str \| None`   | Grouped occupation label                   |
| `included`               | `bool`          | Whether this row passes inclusion criteria |
| `exclusion_reason`       | `str \| None`   | Reason if excluded                         |

---

## Data Layer Files

```
data/
  raw/              # RawIslanderRecord JSON files
  normalized/       # NormalizedIslander JSON files
  analysis/         # AnalysisRow CSV or JSON
```
