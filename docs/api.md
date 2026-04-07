# API Documentation

This document describes the unofficial HTTP surface and the Python client API exposed by `islands-webscraper`.

## Overview

The scraper is built around five main endpoint families:

- village pages
- household pages
- islander pages
- consent requests
- chat requests

These are session-authenticated requests and generally return HTML or ad hoc text, not JSON.

---

## HTTP Endpoint Model

### `GET /village.php?<VillageName>`

Fetch a village page.

#### Purpose

Returns the village HTML, including:

- village id
- island id
- house map array

#### Used for

- discovering household ids in a village
- village-level sampling frame construction

#### Client method

```python
collector.fetch_village("Vardo")
```

#### Returns

```python
VillagePage(
    village_name="Vardo",
    village_id=0,
    island_id=0,
    house_ids=[...],
    raw_html="..."
)
```

---

### `GET /house.php?v=<village_id>&h=<house_id>`

Fetch a household page.

#### Purpose

Returns the household roster HTML.

#### Used for

- listing residents
- filtering eligible adults
- selecting one adult per household

#### Client method

```python
collector.fetch_household(village_id=0, house_id=5)
```

#### Returns

```python
HouseholdPage(
    village_id=0,
    house_id=5,
    residents=[
        Resident(name="Katsuo Ueta", age=35, islander_id="66g8k89vwm"),
        ...
    ],
    raw_html="..."
)
```

---

### `GET /islander.php?id=<islander_id>`

Fetch an islander page.

#### Purpose

Returns the subject profile HTML.

#### Used for

- age
- summary fields
- current residence
- timeline events
- chat id
- awake status

#### Client method

```python
collector.fetch_islander("66g8k89vwm")
```

#### Returns

```python
IslanderPage(
    islander_id="66g8k89vwm",
    name="Katsuo Ueta",
    age=35,
    current_residence="Pauma 5",
    chatid="...",
    awake=False,
    summary_lines=[...],
    timeline_events=[...],
    raw_html="..."
)
```

---

### `GET /php/consent.php?id=<islander_id>`

Request subject consent.

#### Purpose

Triggers the consent flow.

#### Used for

- obtaining study consent before chat/task collection

#### Client method

```python
collector.request_consent("66g8k89vwm")
```

#### Returns

```python
ConsentResponse(
    islander_id="66g8k89vwm",
    outcome="accept",
    message="...",
    raw_text="..."
)
```

---

### `GET /alice.php?<chatid>&<message>`

Send a direct chat question.

#### Purpose

Obtains question/answer responses without using the browser chat box.

#### Used for

- birth village
- income
- occupation
- other survey-like prompts

#### Client method

```python
collector.ask(chatid, "Which village were you born in?")
```

#### Returns

```python
ChatResponse(
    chatid="...",
    question="Which village were you born in?",
    response_text="I was born in Talu.",
    state_updates={},
    raw_text="..."
)
```

---

## Errors

| Error                  | Description                           |
| ---------------------- | ------------------------------------- |
| `AuthenticationError`  | Session is invalid or expired         |
| `RateLimitError`       | Request rate exceeded                 |
| `ParseError`           | Failed to parse HTML/text payload     |
| `ConsentError`         | Consent flow failed or was declined   |
| `ChatUnavailableError` | Subject is asleep or chat unavailable |

The client preserves raw payloads whenever parsing fails.
