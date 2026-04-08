# 🏝️ islands-webscraper 🏝️

A Python CLI and library for structured, reproducible data collection from the Islands teaching simulator.

This project provides:

- an authenticated HTTP client
- HTML/text parsers for observed simulator endpoints
- reproducible household and adult sampling workflows
- consent-aware participant collection
- normalization and minimal analysis-row derivation
- run-scoped persistence for raw/evidence, normalized, and analysis outputs

## Project Status

This is an unofficial utility built around observed site behavior and page JavaScript. It is not an official API client.

The core toolchain is functional and supports:

- village / household / islander inspection
- sampling and reserve replacement workflows
- configurable participant collection
- study-default convenience commands
- normalization and deterministic derivation
- run-scoped save/export workflows
- multi-village study runs

## Features

- Session-authenticated HTTP client
- Village, household, islander, consent, and chat endpoint support
- Random household and adult sampling workflows with reproducible seeds
- Consent-aware collection workflow with reserve replacement
- Configurable participant collection plans
- Study-default convenience commands for the current immigrant / income workflow
- Raw/evidence, normalized, and analysis-layer persistence
- Run-scoped output directories to avoid cross-run file mixing
- CLI interface for inspection, collection, normalization, derivation, and export

## Installation

```bash
pip install -e .
```

For tests and development tools:

```bash
pip install -e .[dev]
```

## Authentication

The simulator requires an authenticated browser session.

The CLI supports:

- guided browser login and cookie import
- manual cookie-header entry
- explicit auth validation

### Guided login

```bash
islands auth-login --browser firefox
```

or

```bash
islands auth-login --browser chrome
```

### Manual cookie entry

```bash
islands auth-set-cookie
```

### Test auth

```bash
islands auth-test
```

### Clear auth

```bash
islands auth-clear
```

## Configuration

Create a `.env` file from `.env.example`.

Typical values:

```env
ISLANDS_BASE_URL=https://islands.smp.uq.edu.au
ISLANDS_COOKIE_HEADER=
ISLANDS_AUTH_CAPTURED_AT=
REQUEST_TIMEOUT_SECONDS=30
REQUEST_BASE_DELAY_SECONDS=1.2
REQUEST_JITTER_MIN_SECONDS=0.4
REQUEST_JITTER_MAX_SECONDS=1.0
DATA_DIR=data
SAVE_DEBUG_PAYLOADS=false
```

## Quick Start

For a full list of the CLI commands and their arguments, you can use the `islands --help` command.

### 1. Log in

```bash
islands auth-login --browser firefox|chrome
```

### 2. Inspect a village

```bash
islands fetch-village Vardo
```

### 3. Inspect a household

```bash
islands fetch-household --village-name Vardo --house-id 5
```

### 4. Inspect an islander

```bash
islands fetch-islander --village-name Vardo --islander-id j4vw2wjwr6
```

### 5. Pilot one study-default village run

```bash
islands collect-study-default-village-and-save --village-name Vardo --n 3 --reserve-n 5 --seed 401
```

### 6. Run a study across multiple villages

In `cmd.exe`:

```bat
islands collect-study-default-data-and-save ^
  --village-name Vardo ^
  --village-name Hofn ^
  --village-name Bjurholm ^
  --n 40 ^
  --reserve-n 20 ^
  --seed 401
```

## Common CLI Workflows

### Inspection

```bash
islands fetch-village Vardo
islands fetch-household --village-name Vardo --house-id 5
islands fetch-islander --village-name Vardo --islander-id j4vw2wjwr6
islands consent --village-name Vardo --islander-id j4vw2wjwr6
islands ask --village-name Vardo --islander-id j4vw2wjwr6 --question "Which village were you born in?"
```

### Sampling only

```bash
islands sample-village --village-name Vardo --n 5 --reserve-n 10 --seed 401
```

### Consent-aware village workflow

```bash
islands collect-village --village-name Vardo --n 5 --reserve-n 10 --seed 401
```

### Configurable participant collection

```bat
islands collect-participant ^
  --village-name Vardo ^
  --islander-id j4vw2wjwr6 ^
  --summary-field age ^
  --summary-field current_residence ^
  --summary-field money_summary ^
  --question "birth_village=Which village were you born in?" ^
  --question "income=What is your income?"
```

### Study-default participant collection

```bash
islands collect-study-default-participant --village-name Vardo --islander-id j4vw2wjwr6
```

### Collect + normalize

```bash
islands collect-study-default-and-normalize-participant --village-name Vardo --islander-id j4vw2wjwr6
```

### Collect + normalize + derive

```bash
islands collect-study-default-and-derive-participant --village-name Vardo --islander-id j4vw2wjwr6
```

### Save one participant run

```bash
islands collect-study-default-and-save-participant --village-name Vardo --islander-id j4vw2wjwr6
```

### Save one village run

```bash
islands collect-study-default-village-and-save --village-name Vardo --n 5 --reserve-n 10 --seed 401
```

### Save a multi-village study run

```bat
islands collect-study-default-data-and-save ^
  --village-name Vardo ^
  --village-name Hofn ^
  --village-name Bjurholm ^
  --n 40 ^
  --reserve-n 20 ^
  --seed 401
```

## Python Example

```python
from scraper.client.session import IslandsSession
from scraper.services.collection import Collector

with IslandsSession.from_config() as session:
    collector = Collector(session)

    village = collector.fetch_village("Vardo")
    print(village.village_id, len(village.house_ids))

    household = collector.fetch_household(village=village, house_id=village.house_ids[0])
    print(household.residents)

    islander = collector.fetch_islander(
        village=village,
        islander_id=household.residents[0].islander_id,
    )
    print(islander.name, islander.chatid)

    consent = collector.request_consent(islander)
    print(consent.outcome, consent.message)

    reply = collector.ask(islander=islander, question="Which village were you born in?")
    print(reply.response_text)
```

## Data Layers

This repo works with three practical layers of data:

| Layer              | Description                                                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Raw / Evidence** | Compact structured evidence such as sampling decisions, processed households, consent outcomes, chat responses, and participant collection records     |
| **Normalized**     | Parsed participant facts such as birth village, current village, money summary value, income signal, and education evidence                            |
| **Analysis**       | Minimal derived fields used in downstream statistical analysis, such as current island, birth island, immigrant status, and compact education labeling |

## Output Model

Outputs are **run-scoped**.

Each save command writes to a new run directory by default:

```
data/
  runs/
    2026-04-07T21-18-03_village-Vardo_n-5_seed-401_ab12cd34/
      raw/
      normalized/
      analysis/
```

For multi-village study runs, the tool writes one study-level run directory with per-village subdirectories plus aggregated study-level analysis outputs.

## Task run interruption and resumption

If study collection tasks are interrupted, they can be resumed by finding the run_state run_id and using the `resume-study-run` command.

## Current Study Defaults

The current convenience commands are set up for the immigrant / income workflow.

### Default summary fields

- `age`
- `current_residence`
- `money_summary`
- `occupation_summary`

### Default chat questions

- `birth_village = Which village were you born in?`
- `income = What is your income?`

These defaults are used by all commands containing `study-default`.

## Testing

Run tests from the repository root:

```bash
pytest
```

Run one test file:

```bash
pytest tests\test_islander_parser.py -v
```

If `pytest` is not recognized:

```bash
python -m pytest -v
```

Current high-value test areas:

- village parser
- house parser
- islander parser
- consent parser
- chat parser
- normalization
- derivation

## Documentation

See the full operator guide:

- [`Full Usage Guide`](docs/islands_full_usage_guide.md)

Additional project docs:

- [`API Reference`](docs/api.md) - HTTP endpoint model, extracted from site network events
- [`Architecture`](docs/architecture.md) - repository structure, layer responsibilities, and design principles
- [`Data Model`](docs/data-model.md) - all Pydantic models across the raw, normalized, and analysis stages
- [`Sampling Policy`](docs/sampling-policy.md) - the project’s sampling methodology, including purposive village choice, random household sampling, reserve handling, and reproducibility policy
- [`Adapting the Tool`](docs/adapting-the-tool.md) - guidance for future users on what is generic, what is configurable, and what is currently shaped around the immigrant / income study
- [`Workflows`](docs/workflows.md) - end-to-end workflow references for common use cases, including village inspection, participant collection, study-default runs, and multi-village study collection

## Notes on Scope

This project intentionally does **not** try to absorb every downstream analysis transform.

Some recodes are better handled after export in R or Python, especially when they are:

- subjective
- likely to change
- study-specific beyond deterministic mapping

Examples include occupation grouping, alternate education bins, custom income bands, and model-specific exclusion rules.

## Rate Limiting and Safety

This utility is intentionally conservative. Requests are sequential by default, with configurable delay and jitter settings to reduce load on the simulator.

> **Note:** This project uses an unofficial interface inferred from observable site behavior and authenticated in-browser requests. Use responsibly.
