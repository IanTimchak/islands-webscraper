# Sampling Policy

This document defines the sampling methodology used by the Islands webscraper.

## Overview

The project uses a multi-stage sampling design.

### Stage 1: Village selection

Villages are **not selected randomly**.

Instead, villages are chosen purposively as the **three largest villages on each island**. This is done to:

- increase coverage of major population centers
- improve the chance of observing inter-island migration
- keep village selection consistent across islands

Because this stage is purposive, results should be interpreted as most representative of adults in the selected larger villages, not necessarily all villages equally.

## Stage 2: Household sampling within a village

Within each selected village, households are sampled **uniformly at random without replacement** from the full household frame parsed from the village page.

The household frame is defined as:

- all internal household ids discovered from the village page map array
- excluding named non-house locations such as schools, halls, clinics, hotels, and empty lots

For each village:

- a primary household sample is generated
- a reserve household list is generated in advance using the same randomization process

Adjacent-household replacement is never used.

## Stage 3: Adult selection within a household

For each sampled household:

- the household roster is fetched
- all residents age **21 or older** are identified as eligible adults
- one eligible adult is selected **uniformly at random**

If no eligible adult is present, the household is marked unusable for primary selection and the next unused reserve household is used.

## Stage 4: Consent

The selected adult is asked to consent to participate in the study.

If the selected adult declines consent:

- that household selection attempt is marked as declined
- the next unused reserve household is used

A person is not included in the final study dataset unless consent is accepted.

## Randomization and reproducibility

All random sampling is performed using a recorded pseudorandom seed.

The following should be stored for each sampling run:

- seed
- selected villages
- household frame size per village
- primary household ids
- reserve household ids
- selected adult per sampled household
- replacement reasons
- consent outcomes

This makes the sampling run reproducible and auditable.

## Summary of methodological guarantees

The scraper should preserve the following guarantees:

- village selection is purposive, not random
- household selection within a village is random without replacement
- adult selection within a household is random among eligible adults
- replacement uses a pre-randomized reserve list
- all exclusions and replacements are logged
- the random seed is recorded
