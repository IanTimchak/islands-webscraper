# Workflows

This document describes the end-to-end collection and dataset build workflows in `islands-webscraper`.

---

## Overview

Data collection moves through three stages:

1. **Raw collection** — fetch and persist raw HTML/text payloads for each subject
2. **Normalization** — parse raw records into structured facts
3. **Analysis build** — derive final analysis variables from normalized records

Each stage is independently resumable and its outputs are persisted to disk before the next stage begins.

---

## Stage 1: Raw Collection

### Goal

Fetch village, household, islander, consent, and chat data for a target sample and persist raw records.

### Steps

1. Fetch the village page for each target village
2. Sample household ids from each village (primary + reserve)
3. For each sampled household, fetch the household page
4. Select one eligible adult (age 21+) per household
5. Fetch the islander page for the selected adult
6. Request consent
7. If consent accepted, ask the minimum chat question set
8. Persist the full `RawIslanderRecord` to `data/raw/`

### CLI

```bash
islands collect raw \
  --villages Vardo Hofn Akkeshi Arcadia Pauma Riroua \
  --per-village 40 \
  --output-dir data/
```

### Resume behavior

Collection checks `data/raw/` for existing records before fetching. Already-collected subjects are skipped.

---

## Stage 2: Normalization

### Goal

Parse raw records into structured `NormalizedIslander` records.

### Steps

1. Load each `RawIslanderRecord` from `data/raw/`
2. Parse age, current village, birth village, income, occupation, and education evidence
3. Persist each `NormalizedIslander` to `data/normalized/`

### CLI

```bash
islands build normalized --input-dir data/ --output-dir data/
```

### Notes

- Normalization is deterministic given the same raw inputs
- Fields that cannot be parsed are set to `None` rather than raising errors
- The raw payload is always preserved for manual review

---

## Stage 3: Analysis Build

### Goal

Derive final analysis variables from normalized records.

### Steps

1. Load each `NormalizedIslander` from `data/normalized/`
2. Derive `immigrant_other_island`, `income`, `education_level`, `occupation_group`
3. Apply inclusion/exclusion criteria and flag each row
4. Persist each `AnalysisRow` to `data/analysis/`

### CLI

```bash
islands build analysis --input-dir data/ --output-dir data/
```

---

## Inspection Workflows

Use `inspect` commands to probe individual records without running full collection.

### Inspect a village

```bash
islands inspect village Vardo
```

### Inspect a household

```bash
islands inspect household --village-id 0 --house-id 5
```

### Inspect an islander

```bash
islands inspect islander 66g8k89vwm
```

---

## Python Workflow Example

```python
from islands_webscraper.client.session import IslandsSession
from islands_webscraper.services.collection import Collector
from islands_webscraper.services.sampling import HouseholdSampler
from islands_webscraper.services.normalization import Normalizer
from islands_webscraper.services.derivation import Deriver

session = IslandsSession.from_env()
collector = Collector(session)
sampler = HouseholdSampler()
normalizer = Normalizer()
deriver = Deriver()

# Fetch village and sample households
village = collector.fetch_village("Vardo")
sample = sampler.sample_households(village.house_ids, n=40, seed=42)

for house_id in sample.primary:
    household = collector.fetch_household(village.village_id, house_id)
    adult = sampler.select_adult(household.residents)
    if adult is None:
        continue

    islander = collector.fetch_islander(adult.islander_id)
    consent = collector.request_consent(adult.islander_id)
    if consent.outcome != "accept":
        continue

    reply = collector.ask(islander.chatid, "Which village were you born in?")

    # Normalize and derive
    normalized = normalizer.normalize_islander(islander, [reply], village_lookup={})
    row = deriver.derive_analysis_row(normalized)
    print(row)
```

---

## Rate Limiting

All HTTP requests are sequential by default. The session applies:

- a configurable base delay between requests
- jitter to avoid fixed-interval patterns
- automatic retry with backoff on transient failures

This project uses an unofficial interface. Use conservatively and responsibly.
