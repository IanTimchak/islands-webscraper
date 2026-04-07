# 🏝️ islands-webscraper 🏝️

A Python utility for structured data collection from the Islands teaching simulator.

This project provides a typed client, HTML/text parsers, and reproducible collection pipelines for sampling villages, households, and islanders, then building raw, normalized, and analysis-ready datasets.

## Features

- Session-authenticated HTTP client
- Village, household, islander, consent, and chat endpoint support
- Random household and adult sampling workflows
- Raw / normalized / analysis-layer exports
- Built-in rate limiting, retry, and resumable collection
- CLI and Python library interfaces

## Project Status

This is an unofficial utility built around observed site behavior and page JavaScript. It is not an official API client.

## Installation

```bash
pip install -e .
```

## Quick Start

### 1. Configure a session

Create a `.env` file from `.env.example` and provide:

```env
ISLANDS_BASE_URL=https://islands.smp.uq.edu.au
ISLANDS_COOKIE_HEADER=your_session_cookie_here
```

### 2. Inspect a village

```bash
islands inspect village Vardo
```

### 3. Run raw collection

```bash
islands collect raw \
  --villages Vardo Hofn Akkeshi Arcadia Pauma Riroua \
  --per-village 40 \
  --output-dir data/
```

### 4. Build normalized dataset

```bash
islands build normalized --input-dir data/ --output-dir data/
```

### 5. Build final analysis dataset

```bash
islands build analysis --input-dir data/ --output-dir data/
```

## Python Example

```python
from islands_webscraper.client.session import IslandsSession
from islands_webscraper.services.collection import Collector

session = IslandsSession.from_env()
collector = Collector(session)

village = collector.fetch_village("Vardo")
print(village.village_id, len(village.house_ids))

household = collector.fetch_household(village_id=village.village_id, house_id=village.house_ids[0])
print(household.residents)

islander = collector.fetch_islander(household.residents[0].islander_id)
print(islander.name, islander.chatid)

collector.request_consent(islander.islander_id)
reply = collector.ask(islander.chatid, "Which village were you born in?")
print(reply.response_text)
```

## Data Layers

This repo stores data in three layers:

| Layer          | Description                                                                                |
| -------------- | ------------------------------------------------------------------------------------------ |
| **Raw**        | Original HTML/text payloads from the simulator                                             |
| **Normalized** | Parsed structured facts such as birth village, current village, income, education evidence |
| **Analysis**   | Minimal final variables used in statistical analysis                                       |

## CLI Commands

### Inspect

```bash
islands inspect village <VILLAGE_NAME>
islands inspect household --village-id <ID> --house-id <ID>
islands inspect islander <ISLANDER_ID>
```

### Collection

```bash
islands collect raw --villages ... --per-village 40
```

### Dataset builds

```bash
islands build normalized
islands build analysis
```

## Output

Default output structure:

```
data/
├── raw/
├── normalized/
└── analysis/
```

## Rate Limiting

This utility is intentionally conservative. Requests are sequential by default, with configurable delays, jitter, and retries.

> **Note:** This project uses an unofficial interface inferred from publicly observable site behavior and authenticated in-browser requests. Use responsibly.
