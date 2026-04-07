# Adapting the Tool

This project has both reusable infrastructure and study-shaped layers.

The lower-level parts of the scraper are meant to be reusable. The higher-level normalization and derivation layers in the current project are shaped around the immigrant-income study used for this workflow.

## What is generic

These parts should be reusable with minimal or no changes:

- session and auth bootstrap
- endpoint path construction
- raw page fetching
- village / household / islander / chat / consent parsers
- sampling workflow
- reserve replacement workflow
- configurable participant collection service

These layers are designed as general scraping and collection infrastructure for the Islands simulator.

## What is semi-configurable

These parts are designed to be configured for a study:

- participant collection plan
- summary fields collected from the islander page
- chat questions
- whether timeline events are included

Most users adapting the project should start here.

## What is currently study-shaped

These parts are currently aligned to the immigrant-income study:

- normalized participant schema
- field names such as:
  - `birth_village`
  - `income_response_raw`
  - `money_summary`
  - `current_residence`
- derivations built from village/island movement
- assumptions about which chat responses matter

These layers may need to be changed for a different research task.

## What is intentionally left out of the scraper

Some transforms are better handled after export in R or Python, especially when they are:

- subjective
- likely to change
- part of exploratory analysis

Examples:

- occupation grouping
- education recoding into custom bins
- alternate income bands
- custom exclusion rules for modeling

## How to adapt the project for a different study

### 1. Change the participant collection plan

Update the summary fields and chat questions collected.

### 2. Change the normalization layer

Modify `NormalizationService` and `NormalizedParticipant` to store the structured fields relevant to the new study.

### 3. Change the derivation layer

Modify or replace `DerivationService` and `AnalysisRow` if the final analytical variables differ from the current project.

### 4. Keep the raw collection layers stable

Try not to rewrite the lower-level scraping code unless the simulator itself changes. Most adaptation should happen in:

- collection plans
- normalization
- derivation
- downstream analysis transforms
