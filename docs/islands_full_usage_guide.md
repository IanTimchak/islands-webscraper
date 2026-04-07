# Islands Webscraper — Full Usage Guide

## Overview

This guide covers the full operator workflow for the Islands webscraper project:

- authentication
- inspection and debugging commands
- sampling commands
- participant collection commands
- normalization and derivation commands
- save/export commands
- multi-village study runs
- output layout
- testing and validation
- adaptation guidance

This document is written for day-to-day use of the tool, not just for developers reading the source.

---

## 1. What this tool does

The Islands webscraper is a run-oriented command-line tool for interacting with the Islands simulator in a structured, reproducible way.

At a high level, it supports:

1. authenticating against the simulator
2. fetching and parsing villages, households, and islanders
3. sampling households and adults reproducibly
4. requesting consent
5. collecting configurable participant data
6. normalizing collected results into structured facts
7. deriving a minimal analysis-ready row
8. saving outputs into run-scoped directories

The tool is designed in layers.

### Layer 1: scraping and collection infrastructure

This layer includes:

- auth/session handling
- endpoint calls
- village / household / islander / consent / chat parsing
- sampling workflow
- reserve replacement workflow

### Layer 2: configurable collection

This layer includes:

- configurable summary-field collection
- configurable chat-question collection
- optional timeline inclusion

### Layer 3: study-shaped normalization and derivation

This layer includes:

- the current normalized participant shape
- the current derivation shape for immigrant status
- current-study convenience commands

The lower layers are the most reusable. The higher layers are more aligned with the current immigrant / income study.

---

## 2. Project assumptions

This guide assumes:

- the package is installed and the `islands` CLI command is available
- you are running commands from the repository root or from an environment where the entry point is installed
- `.env` is used for auth and runtime settings
- output is written into run-scoped directories under `data/runs/`

---

## 3. Authentication

The simulator requires an authenticated browser session. The tool supports two ways of getting that auth into the CLI.

### 3.1 Guided browser login

Use this when you want the CLI to open the site and import cookies from a browser profile:

```bash
islands auth-login --browser firefox
```

or

```bash
islands auth-login --browser chrome
```

What it does:

1. opens the Islands site in the selected browser
2. waits for you to log in manually
3. imports cookies from that browser profile
4. stores the cookie header in `.env`
5. runs one live auth validation

Useful options:

- `--browser chrome`
- `--browser firefox`
- `--no-open` if you do not want the CLI to open the browser automatically

Example:

```bash
islands auth-login --browser firefox --no-open
```

### 3.2 Manual cookie entry

Use this if browser cookie import does not work:

```bash
islands auth-set-cookie
```

The CLI will prompt you to paste a cookie header string such as:

```text
PHPSESSID=...; other_cookie=...
```

It will then store it in `.env` and validate it once.

### 3.3 Check whether auth is still valid

```bash
islands auth-test
```

This performs an explicit live auth check.

### 3.4 Clear stored auth

```bash
islands auth-clear
```

This removes the saved cookie and timestamp from `.env`.

### 3.5 Auth freshness behavior

The tool uses a local freshness guard before most authenticated commands.

That means:

- it checks that auth exists
- it checks that auth is not stale
- it does **not** live-hit the server before every normal command

A live check is only done when it makes sense, such as after auth setup.

---

## 4. Inspection commands

These commands are useful for debugging and understanding the simulator structure before running full workflows.

### 4.1 Fetch a village

```bash
islands fetch-village Vardo
```

This prints:

- village name
- village id
- island id
- household count

Use this to confirm the village exists and that the parser is working.

### 4.2 Fetch a household

```bash
islands fetch-household --village-name Vardo --house-id 5
```

This prints:

- village id
- internal house id
- displayed house number, if available
- resident list with ages and islander ids

Important note:

- internal house ids are request ids used by `house.php`
- displayed house numbers may differ because the simulator labels houses for display in a different way

### 4.3 Fetch an islander

```bash
islands fetch-islander --village-name Vardo --islander-id j4vw2wjwr6
```

This prints the parser’s main islander fields, including:

- name
- islander id
- chat id
- awake flag
- age
- money summary
- current residence
- occupation summary
- timeline event count

### 4.4 Ask for consent

```bash
islands consent --village-name Vardo --islander-id j4vw2wjwr6
```

This prints the parsed consent response:

- outcome
- timestamp text
- message

### 4.5 Ask a direct chat question

```bash
islands ask --village-name Vardo --islander-id j4vw2wjwr6 --question "Which village were you born in?"
```

This prints:

- the question
- the chat id
- the parsed response text
- any state updates returned by the backend

Use this for exploratory debugging and endpoint verification.

---

## 5. Sampling commands

These commands execute the reproducible household/adult selection logic.

### 5.1 Sample one village

```bash
islands sample-village --village-name Vardo --n 5 --reserve-n 10 --seed 401
```

This runs the sampling slice only:

- random household sampling without replacement
- reserve-list generation
- eligible-adult filtering
- random adult selection per household

It does **not** request consent and does **not** collect chat data.

Key options:

- `--village-name`
- `--n` number of primary households
- `--reserve-n` reserve households to pre-generate
- `--seed` reproducible seed
- `--min-age` adult threshold, default 21

### 5.2 Consent-aware village workflow

```bash
islands collect-village --village-name Vardo --n 5 --reserve-n 10 --seed 401
```

This runs the consent-aware workflow:

- sample households
- pick one eligible adult
- request consent
- use reserve households when needed
- stop when target completed participants is reached

This command is useful when you want to test the consent/replacement workflow without yet collecting configurable participant data.

Useful option:

- `--progress-level 0|1|2`

Progress levels:

- `0` top-level run progress
- `1` household-level progress
- `2` detailed step-by-step progress

---

## 6. Generic participant collection commands

These commands are the reusable collection layer.

### 6.1 Collect one participant with a configurable plan

```bash
islands collect-participant ^
  --village-name Vardo ^
  --islander-id j4vw2wjwr6 ^
  --summary-field age ^
  --summary-field current_residence ^
  --summary-field money_summary ^
  --question "birth_village=Which village were you born in?" ^
  --question "income=What is your income?"
```

What it does:

- fetches the islander using the correct context
- collects the requested summary fields
- asks the requested chat questions
- optionally includes timeline events
- prints the collected result

Key options:

- `--summary-field <field>` repeated
- `--question "key=Question text"` repeated
- `--include-timeline / --no-include-timeline`
- `--progress-level`

### 6.2 Study-default participant collection

The current project uses a recurring set of fields/questions.

The convenience command for that is:

```bash
islands collect-study-default-participant --village-name Vardo --islander-id j4vw2wjwr6
```

Current defaults:

Summary fields:
- `age`
- `current_residence`
- `money_summary`
- `occupation_summary`

Chat questions:
- `birth_village = Which village were you born in?`
- `income = What is your income?`

Use this command when you want the current project’s default participant collection without retyping every field and question.

---

## 7. Normalization commands

Normalization converts collected participant results into structured facts.

It stays closer to the evidence than the final analysis layer.

### 7.1 Collect and normalize a participant with a configurable plan

```bash
islands collect-and-normalize-participant ^
  --village-name Vardo ^
  --islander-id j4vw2wjwr6 ^
  --summary-field age ^
  --summary-field current_residence ^
  --summary-field money_summary ^
  --summary-field occupation_summary ^
  --question "birth_village=Which village were you born in?" ^
  --question "income=What is your income?"
```

This produces normalized fields such as:

- `age`
- `current_residence_raw`
- `current_village`
- `current_house_number`
- `money_summary_raw`
- `money_summary_value`
- `birth_village_raw`
- `birth_village`
- `income_response_raw`
- `income_numeric`
- `income_text_normalized`
- `occupation_summary_raw`
- `occupation_chat_raw`
- `occupation_from_income_raw`
- `occupation_text`
- `education_events`

### 7.2 Study-default normalize command

```bash
islands collect-study-default-and-normalize-participant --village-name Vardo --islander-id j4vw2wjwr6
```

This uses the current study’s default fields/questions and prints the normalized participant.

### 7.3 Notes on normalization scope

Normalization in the current project is already somewhat study-shaped.

It is not intended to be the universal schema for all future Islands studies.

That is acceptable.

The reusable part is the collection engine. The current normalization schema is a convenience layer for this project.

---

## 8. Derivation commands

Derivation is the minimal analysis-facing layer currently implemented in-tool.

Right now it does only deterministic mapping:

- current village → current island
- birth village → birth island
- immigrant_other_island
- latest education event
- education label

It intentionally does **not** do:

- occupation grouping
- broad dataset recodes
- subjective transforms better handled downstream

### 8.1 Collect, normalize, and derive with a configurable plan

```bash
islands collect-normalize-derive-participant ^
  --village-name Vardo ^
  --islander-id j4vw2wjwr6 ^
  --summary-field age ^
  --summary-field current_residence ^
  --summary-field money_summary ^
  --summary-field occupation_summary ^
  --question "birth_village=Which village were you born in?" ^
  --question "income=What is your income?"
```

This prints the analysis row fields.

### 8.2 Study-default derive command

```bash
islands collect-study-default-and-derive-participant --village-name Vardo --islander-id j4vw2wjwr6
```

Use this when you want the current study’s standard output with minimal typing.

---

## 9. Full village workflow commands

These commands combine sampling, consent, replacement, and participant collection.

### 9.1 Configurable village workflow

```bash
islands collect-village-data ^
  --village-name Vardo ^
  --n 5 ^
  --reserve-n 10 ^
  --seed 401 ^
  --summary-field age ^
  --summary-field current_residence ^
  --summary-field money_summary ^
  --summary-field occupation_summary ^
  --question "birth_village=Which village were you born in?" ^
  --question "income=What is your income?"
```

This runs:

- household sampling
- reserve replacement
- adult selection
- consent requests
- participant collection

It prints a collected-participant summary at the end.

### 9.2 Study-default village workflow

```bash
islands collect-study-default-village --village-name Vardo --n 5 --reserve-n 10 --seed 401
```

This is the easiest command for your current project when you want one village at a time.

---

## 10. Save/export commands

The tool uses **run-scoped persistence**.

This means:

- each save command writes into a new run directory by default
- JSONL appends only within that run
- outputs from different runs are not mixed into the same files unless you explicitly reuse a run id

### 10.1 Save one participant with a configurable plan

```bash
islands collect-normalize-derive-and-save-participant ^
  --village-name Vardo ^
  --islander-id j4vw2wjwr6 ^
  --summary-field age ^
  --summary-field current_residence ^
  --summary-field money_summary ^
  --summary-field occupation_summary ^
  --question "birth_village=Which village were you born in?" ^
  --question "income=What is your income?"
```

This writes:

- `raw/participant_collection.jsonl`
- `normalized/participants.jsonl`
- `analysis/analysis_rows.jsonl`
- `analysis/analysis_rows.csv`

inside a run-scoped directory.

### 10.2 Save one participant with study defaults

```bash
islands collect-study-default-and-save-participant --village-name Vardo --islander-id j4vw2wjwr6
```

### 10.3 Save one village workflow with a configurable plan

```bash
islands collect-village-data-and-save ^
  --village-name Vardo ^
  --n 5 ^
  --reserve-n 10 ^
  --seed 401 ^
  --summary-field age ^
  --summary-field current_residence ^
  --summary-field money_summary ^
  --summary-field occupation_summary ^
  --question "birth_village=Which village were you born in?" ^
  --question "income=What is your income?"
```

This writes a run-scoped village workflow output directory containing:

- raw sampling run metadata
- processed household audit records
- participant collection records
- normalized participant records
- analysis rows in JSONL and CSV

### 10.4 Save one village workflow with study defaults

```bash
islands collect-study-default-village-and-save --village-name Vardo --n 5 --reserve-n 10 --seed 401
```

---

## 11. Multi-village study commands

These commands are the main top-level entry point for your actual sampling scheme.

### 11.1 Multi-village configurable study run

```bash
islands collect-study-data-and-save ^
  --village-name Vardo ^
  --village-name Hofn ^
  --village-name Bjurholm ^
  --n 40 ^
  --reserve-n 20 ^
  --seed 401 ^
  --summary-field age ^
  --summary-field current_residence ^
  --summary-field money_summary ^
  --summary-field occupation_summary ^
  --question "birth_village=Which village were you born in?" ^
  --question "income=What is your income?"
```

This command:

- reuses the single-village workflow internally
- processes each listed village in sequence
- saves one study-scoped run directory
- creates one subdirectory per village
- writes aggregated study-level analysis outputs

### 11.2 Multi-village study run with defaults

```bash
islands collect-study-default-data-and-save ^
  --village-name Vardo ^
  --village-name Hofn ^
  --village-name Bjurholm ^
  --n 40 ^
  --reserve-n 20 ^
  --seed 401
```

This is the primary convenience command for your current project.

Use this when you want to execute your actual study design without retyping the same summary fields and chat questions every time.

---

## 12. Output layout

All save commands use **run-scoped output directories**.

### 12.1 Example participant run

```text
data/
  runs/
    2026-04-07T21-18-03_participant-j4vw2wjwr6_village-Vardo_ab12cd34/
      raw/
        participant_collection.jsonl
      normalized/
        participants.jsonl
      analysis/
        analysis_rows.jsonl
        analysis_rows.csv
```

### 12.2 Example village run

```text
data/
  runs/
    2026-04-07T21-18-03_village-Vardo_n-5_seed-401_ab12cd34/
      raw/
        sampling_runs.jsonl
        processed_households.jsonl
        participant_collection.jsonl
      normalized/
        participants.jsonl
      analysis/
        analysis_rows.jsonl
        analysis_rows.csv
```

### 12.3 Example study run

```text
data/
  runs/
    2026-04-07T21-18-03_study_Vardo-Hofn-Bjurholm_n-40_seed-401_ab12cd34/
      raw/
        study_run.jsonl
        village_summaries.jsonl
      analysis/
        analysis_rows.jsonl
        analysis_rows.csv
      villages/
        village-Vardo/
          raw/
          normalized/
          analysis/
        village-Hofn/
          raw/
          normalized/
          analysis/
        village-Bjurholm/
          raw/
          normalized/
          analysis/
```

### 12.4 Why the outputs are structured this way

The run-scoped design exists to avoid accidental concatenation of unrelated runs.

JSONL is append-only **within a run**, not across all time.

This keeps:

- runs isolated
- auditability clear
- deletion/retry easy
- CSV export clean

---

## 13. Raw vs normalized vs analysis outputs

### Raw/evidence layer

This is not “full HTML dumped everywhere.”

Instead, it stores compact structured evidence such as:

- sampling decisions
- processed household records
- participant collection records
- chat outputs
- consent outcomes

This is enough to audit or re-normalize later without exploding file size.

### Normalized layer

This stores structured participant facts derived from the collected evidence.

It is closer to your study shape, but still keeps the evidence clearer than the final analysis row.

### Analysis layer

This stores the compact analysis-facing row.

At the moment, it includes deterministic derivations such as immigrant status and compact education fields.

---

## 14. Progress output

Many workflow commands support:

```text
--progress-level 0|1|2
```

Suggested usage:

- `0` for top-level run summaries
- `1` for normal workflow use
- `2` for debugging

The current system uses a lightweight progress reporter, not heavy nested progress bars.

This was intentional so large workflows remain readable.

---

## 15. Run ids

Save commands generate descriptive run ids by default.

Examples:

```text
2026-04-07T21-18-03_participant-j4vw2wjwr6_village-Vardo_ab12cd34
2026-04-07T21-18-03_village-Vardo_n-5_seed-401_ab12cd34
2026-04-07T21-18-03_study_Vardo-Hofn-Bjurholm_n-40_seed-401_ab12cd34
```

You can also override the run id manually:

```bash
islands collect-study-default-data-and-save --village-name Vardo --n 40 --run-id pilot-run-01
```

Use manual run ids sparingly. The generated ones are usually safer.

---

## 16. Current study defaults

The tool includes convenience commands for the current immigrant / income study.

### Current default summary fields

- `age`
- `current_residence`
- `money_summary`
- `occupation_summary`

### Current default chat questions

- `birth_village = Which village were you born in?`
- `income = What is your income?`

These defaults are used by commands whose names include `study-default`.

---

## 17. What is not handled in-tool on purpose

Some transforms are intentionally left for downstream analysis in R or Python.

Examples:

- occupation grouping
- alternate education recodes
- custom income bands
- subjective inclusion or exclusion rules

This is deliberate.

The CLI is strongest at:

- collection
- normalization
- deterministic derivation
- structured output

It is not meant to absorb every downstream analysis choice.

---

## 18. Recommended operator workflows

### 18.1 Quick auth check

```bash
islands auth-test
```

### 18.2 Inspect a village and one household

```bash
islands fetch-village Vardo
islands fetch-household --village-name Vardo --house-id 5
```

### 18.3 Inspect one islander

```bash
islands fetch-islander --village-name Vardo --islander-id j4vw2wjwr6
```

### 18.4 Test collection defaults on one participant

```bash
islands collect-study-default-participant --village-name Vardo --islander-id j4vw2wjwr6
```

### 18.5 Test normalization + derivation on one participant

```bash
islands collect-study-default-and-derive-participant --village-name Vardo --islander-id j4vw2wjwr6
```

### 18.6 Pilot one village run

```bash
islands collect-study-default-village-and-save --village-name Vardo --n 3 --reserve-n 5 --seed 401
```

### 18.7 Run the actual study across multiple villages

```bash
islands collect-study-default-data-and-save ^
  --village-name Vardo ^
  --village-name Hofn ^
  --village-name Bjurholm ^
  --village-name Reading ^
  --village-name Arcadia ^
  --village-name Akkeshi ^
  --village-name Pauma ^
  --village-name Valais ^
  --village-name Talu ^
  --n 40 ^
  --reserve-n 20 ^
  --seed 401
```

---

## 19. Testing

Run tests from the repository root with `pytest`.

### Run all tests

```bash
pytest
```

### Run one test file

```bash
pytest tests\test_islander_parser.py -v
```

### Run one subset by name

```bash
pytest tests\test_normalization.py -k income -v
```

### If `pytest` is not found

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

---

## 20. Common pitfalls

### 20.1 Auth works in browser but CLI fails

Run:

```bash
islands auth-test
```

If needed:

- rerun `auth-login`
- or use `auth-set-cookie`

### 20.2 Repeated runs produce different consent behavior

Consent is stateful in the simulator. If someone already consented, the payload can differ from the first run.

This is expected.

### 20.3 JSONL files do not replace old runs

They should not. Outputs are run-scoped now. Each save command writes to its own run directory by default.

### 20.4 Study commands are verbose in `cmd.exe`

Use `^` for multiline continuation in `cmd.exe`.

Use repeated `--village-name` for multi-village runs.

### 20.5 Some recodes are not in the tool

That is intentional. Do subjective grouping and alternate transforms after export.

---

## 21. Adapting the project

If you want to repurpose the tool for another study, the main adaptation points are:

1. **Collection plan**
   - change summary fields
   - change chat questions

2. **Normalization**
   - change the normalized participant schema
   - change the parsing logic for collected evidence

3. **Derivation**
   - change deterministic derived variables
   - or remove them entirely if not needed

Try not to rewrite the lower-level scraping and workflow layers unless the simulator itself changes.

Those lower layers are the most reusable part of the project.

---

## 22. Final notes

This tool is strongest when used in this order:

1. authenticate
2. inspect
3. pilot one participant
4. pilot one village
5. run the full study
6. inspect saved outputs
7. perform any subjective recodes downstream

That keeps the workflow reproducible, understandable, and easy to debug.
