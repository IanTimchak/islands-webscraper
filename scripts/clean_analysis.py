#!/usr/bin/env python3
"""
build_model_dataset.py

Create a reduced analysis dataset from the scraper's analysis CSV.

Default output variables:
- labor_group
- income
- age
- education
- immigrant

Optional:
- include a name column
- anonymize names into anon_00001 style IDs
- generate the old occupation-level style instead of labor-group style

Default coding: labor_group
- 0 = unemployed
- 1 = low-status / routine labor / service / farming
- 2 = skilled trade / artisan / mid-status applied work
- 3 = professional / academic / senior leadership
- 4 = retired

Old/legacy coding: occupation_level
- 0 = unemployed
- 1 = low
- 2 = middle
- 3 = high

Education coding:
- 0 = no graduation event
- 1 = high school
- 2 = university

Notes:
- Default mode distinguishes retired from unemployed:
  - blank occupation and age >= 60 -> retired
  - blank occupation and age < 60 -> unemployed
- Legacy mode preserves the old generation style:
  - blank occupation -> unemployed
  - no retired category
- Club memberships / associations / student status are treated as non-occupational.
- No rows are dropped.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Optional


# ---------------------------------
# Occupation-to-tier recode mapping
# ---------------------------------
OCCUPATION_LEVEL = {
    # Non-occupational / not a job
    "Swimming Club": 0,
    "Book Club": 0,
    "Horticultural Association": 0,
    "Cycling Club": 0,
    "University student": 0,
    "Speleological Society": 0,
    "Running Club": 0,
    "Painting Collective": 0,
    "Chess Club": 0,
    "Ornithological Society": 0,
    # Low
    "Tea Farmer": 1,
    "Bee Keeper": 1,
    "Gardener": 1,
    "Waiter": 1,
    "Shearer": 1,
    "Poultry Farmer": 1,
    "Oat Farmer": 1,
    "Pig Farmer": 1,
    "Lumberjack": 1,
    "Wheat Farmer": 1,
    "Fisherman": 1,
    "Coffee Farmer": 1,
    "Garbage Collector": 1,
    "Dairy Farmer": 1,
    "Postman": 1,
    "Cotton Farmer": 1,
    "Potato Farmer": 1,
    "Kitchen Hand": 1,
    "Hunter": 1,
    "Sheep Farmer": 1,
    "Nanny": 1,
    "Sugarcane Farmer": 1,
    "Cleaner": 1,
    "Barista": 1,
    "Doorman": 1,
    "Flower Farmer": 1,
    "Apple Farmer": 1,
    "Chimney Sweep": 1,  # moved from 2: manual/routine, low barrier
    "Pet Groomer": 1,    # moved from 2: low-skill service
    "Hairdresser": 1,    # moved from 2: licensed but low-status trade
    "Coachman": 1,       # moved from 2: driver/transport labor
    "Tour Guide": 1,     # moved from 2: low barrier, service role
    "Magician": 1,       # moved from 2: entertainment, no formal credential
    # Middle
    "Plumber": 2,
    "Actor": 2,
    "Midwife": 2,
    "Accountant": 2,
    "Jeweller": 2,
    "Arborist": 2,
    "Constable": 2,
    "Turner": 2,
    "Bureaucrat": 2,
    "Nurse": 2,
    "Glazier": 2,
    "Elementary School Teacher": 2,
    "High School Teacher": 2,
    "Massage Therapist": 2,
    "Butcher": 2,
    "Cabinetmaker": 2,
    "Dressmaker": 2,
    "Musician": 2,
    "Brewer": 2,
    "Toymaker": 2,
    "Detective": 2,
    "Sculptor": 2,
    "Dancer": 2,
    "Chef": 2,
    "Librarian": 2,
    "Plasterer": 2,
    "Bricklayer": 2,
    "Acupuncturist": 2,
    "Tailor": 2,
    "Stonemason": 2,
    "Painter": 2,
    "Engraver": 2,
    "Courtesan": 2,
    "Perfumer": 2,
    "Apothecary": 2,
    "Physiotherapist": 2,
    "Audiologist": 2,
    "Speech Therapist": 2,
    "Author": 2,
    "Joiner": 2,
    "Shipwright": 2,
    "Journalist": 2,
    "Wine Maker": 2,
    "Confectioner": 2,
    "Potter": 2,
    "Calligrapher": 2,
    "Nutritionist": 2,    # moved from 3: variable credentialing
    "Hotel Manager": 2,   # moved from 3: managerial but not licensed profession
    "Carpenter": 2,       # moved from 1: skilled trade by definition
    "Baker": 2,           # moved from 1: craft skill, often own business
    "Sailor": 2,          # moved from 1: requires navigation/specialized skill
    "Miller": 2,          # moved from 1: operates machinery, often business owner
    "Sawyer": 2,          # moved from 1: skilled lumber processing
    "Florist": 2,         # moved from 1: creative/design, often self-employed
    "Concierge": 2,       # moved from 1: service management, requires expertise
    "Park Ranger": 2,     # moved from 1: trained, law enforcement + conservation
    # High
    "Elementary School Principal": 3,
    "Education Professor": 3,
    "Doctor": 3,
    "High School Principal": 3,
    "Agriculture Professor": 3,
    "Judge": 3,
    "Mayor of Pauma": 3,
    "Cardiologist": 3,
    "Science Professor": 3,
    "Society Professor": 3,
    "Law Professor": 3,
    "Architecture Professor": 3,
    "Mathematics Professor": 3,
    "Tinkering Professor": 3,
    "Health Professor": 3,
    "Architect": 3,
    "Lawyer": 3,
    "Dentist": 3,         # moved from 2: full professional degree, same tier as Doctor
    "Historian": 3,       # moved from 2: typically academic with advanced degree
    "Botanist": 3,        # moved from 2: scientific professional, usually PhD-level
    # Retired
    # (none listed, but 4 = retired per scheme)
}


# ---------------------------------
# Generic helpers
# ---------------------------------
def normalize_text(value: str | None) -> str:
    """Normalize whitespace and safely convert None to an empty string."""
    if value is None:
        return ""
    return " ".join(value.strip().split())


def parse_optional_int(value: str | None) -> Optional[int]:
    """Parse an integer-like value, returning None when blank or invalid."""
    text = normalize_text(value)
    if not text:
        return None

    try:
        return int(float(text))
    except ValueError:
        return None


def parse_optional_bool(value: str | None) -> Optional[int]:
    """
    Convert boolean-like text into 0/1.

    Returns:
    - 1 for true
    - 0 for false
    - None when blank or unrecognized
    """
    text = normalize_text(value).lower()
    if not text:
        return None

    if text in {"true", "1", "yes"}:
        return 1
    if text in {"false", "0", "no"}:
        return 0

    return None


def resolve_column(
    row: dict[str, str],
    explicit_col: str | None,
    fallbacks: list[str],
) -> str | None:
    """Return the first matching column name present in the row."""
    candidates: list[str] = []
    if explicit_col:
        candidates.append(explicit_col)
    candidates.extend(fallbacks)

    for col in candidates:
        if col in row:
            return col
    return None


def resolve_name(row: dict[str, str], explicit_name_col: str | None) -> str:
    """Find the best available name column."""
    candidates: list[str] = []
    if explicit_name_col:
        candidates.append(explicit_name_col)

    candidates.extend(["islander_name", "name", "participant_name"])

    for col in candidates:
        if col in row:
            return normalize_text(row.get(col))

    return ""


# ---------------------------------
# Variable recoders
# ---------------------------------
def recode_education(raw_value: str | None) -> Optional[int]:
    """
    Recode education into:
    0 = no graduation event
    1 = high school
    2 = university
    """
    text = normalize_text(raw_value).lower()

    if not text:
        return None
    if text == "no_graduation_event":
        return 0
    if text == "high_school":
        return 1
    if text == "university":
        return 2

    # Fallback matching for small format drift
    if "no graduation" in text:
        return 0
    if "high school" in text or "high_school" in text:
        return 1
    if "university" in text:
        return 2

    return None


def recode_occupation_level_legacy(raw_occupation: str | None) -> Optional[int]:
    """
    Old generation style:
    - blank occupation -> unemployed (0)
    - mapped occupations -> 1/2/3
    - non-occupational or unknown nonblank values -> None
    """
    text = normalize_text(raw_occupation)

    if not text:
        return 0

    return OCCUPATION_LEVEL.get(text)


def recode_labor_group(age_value: str | None, raw_occupation: str | None) -> Optional[int]:
    """
    Default generation style:
    - blank occupation and age >= 60 -> retired (4)
    - blank occupation and age < 60 -> unemployed (0)
    - mapped occupations -> 1/2/3
    - non-occupational or unknown nonblank values -> None
    """
    age = parse_optional_int(age_value)
    text = normalize_text(raw_occupation)

    if not text:
        if age is not None and age >= 60:
            return 4
        return 0

    return OCCUPATION_LEVEL.get(text)


# ---------------------------------
# Core transformation
# ---------------------------------
def build_model_dataset(
    input_csv: Path,
    output_csv: Path,
    include_name: bool,
    anonymize_name: bool,
    legacy_generation: bool,
    age_col: str | None,
    income_col: str | None,
    education_col: str | None,
    immigrant_col: str | None,
    occupation_col: str | None,
    name_col: str | None,
) -> None:
    """
    Read the full analysis CSV and write the reduced modeling dataset.

    In default mode, the first modeled variable is labor_group.
    In legacy mode, the first modeled variable is occupation_level.
    """
    with input_csv.open("r", newline="", encoding="utf-8-sig") as infile:
        reader = csv.DictReader(infile)
        if reader.fieldnames is None:
            raise ValueError("Input CSV appears to have no header row.")

        rows_out: list[dict[str, object]] = []
        anon_counter = 1
        unmapped_occupations: dict[str, int] = {}

        for row in reader:
            resolved_age_col = resolve_column(row, age_col, ["age"])
            resolved_income_col = resolve_column(
                row,
                income_col,
                ["income_numeric", "income", "money_summary_value"],
            )
            resolved_education_col = resolve_column(
                row,
                education_col,
                ["education_label", "education"],
            )
            resolved_immigrant_col = resolve_column(
                row,
                immigrant_col,
                ["immigrant_other_island", "immigrant"],
            )
            resolved_occupation_col = resolve_column(
                row,
                occupation_col,
                ["occupation_text", "occupation", "occupation_summary_raw"],
            )

            if resolved_age_col is None:
                raise ValueError("Could not find an age column.")
            if resolved_income_col is None:
                raise ValueError("Could not find an income column.")
            if resolved_education_col is None:
                raise ValueError("Could not find an education column.")
            if resolved_immigrant_col is None:
                raise ValueError("Could not find an immigrant-status column.")
            if resolved_occupation_col is None:
                raise ValueError("Could not find an occupation column.")

            age_raw = row.get(resolved_age_col)
            occupation_raw = row.get(resolved_occupation_col)
            raw_occupation_text = normalize_text(occupation_raw)

            if legacy_generation:
                primary_status = recode_occupation_level_legacy(occupation_raw)
                primary_column_name = "occupation_level"
            else:
                primary_status = recode_labor_group(age_raw, occupation_raw)
                primary_column_name = "labor_group"

            if raw_occupation_text and primary_status is None:
                unmapped_occupations[raw_occupation_text] = (
                    unmapped_occupations.get(raw_occupation_text, 0) + 1
                )

            age = parse_optional_int(age_raw)
            income = parse_optional_int(row.get(resolved_income_col))
            education = recode_education(row.get(resolved_education_col))
            immigrant = parse_optional_bool(row.get(resolved_immigrant_col))

            out_row: dict[str, object] = {}

            if include_name:
                raw_name = resolve_name(row, name_col)
                if anonymize_name:
                    out_row["name"] = f"anon_{anon_counter:05d}"
                    anon_counter += 1
                else:
                    out_row["name"] = raw_name

            out_row[primary_column_name] = primary_status
            out_row["income"] = income
            out_row["age"] = age
            out_row["education"] = education
            out_row["immigrant"] = immigrant

            rows_out.append(out_row)

    fieldnames: list[str] = []
    if include_name:
        fieldnames.append("name")

    if legacy_generation:
        fieldnames.append("occupation_level")
    else:
        fieldnames.append("labor_group")

    fieldnames.extend(["income", "age", "education", "immigrant"])

    with output_csv.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"Wrote {len(rows_out)} rows to {output_csv}")

    if legacy_generation:
        print("Generation mode: legacy occupation_level")
    else:
        print("Generation mode: default labor_group")

    if unmapped_occupations:
        print("\nNon-occupational or unmapped occupation values encountered:")
        for occ, count in sorted(unmapped_occupations.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {occ}: {count}")


# ---------------------------------
# CLI
# ---------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a reduced modeling dataset from an analysis CSV. "
            "Default mode outputs labor_group; use --legacy-generation "
            "to output the old occupation_level style."
        )
    )

    parser.add_argument("input_csv", type=Path, help="Path to the input analysis CSV.")
    parser.add_argument("output_csv", type=Path, help="Path to the output reduced CSV.")

    parser.add_argument(
        "--include-name",
        action="store_true",
        help="Include a name column in the output.",
    )
    parser.add_argument(
        "--anonymize-name",
        action="store_true",
        help="If names are included, replace them with anon_00001 style IDs.",
    )
    parser.add_argument(
        "--legacy-generation",
        action="store_true",
        help=(
            "Use the old output style. "
            "Blank occupation becomes occupation_level=0 and no retired category is used."
        ),
    )

    parser.add_argument("--age-col", default=None, help="Override the age column name.")
    parser.add_argument("--income-col", default=None, help="Override the income column name.")
    parser.add_argument("--education-col", default=None, help="Override the education column name.")
    parser.add_argument("--immigrant-col", default=None, help="Override the immigrant column name.")
    parser.add_argument("--occupation-col", default=None, help="Override the occupation column name.")
    parser.add_argument("--name-col", default=None, help="Override the name column name.")

    args = parser.parse_args()

    if args.anonymize_name and not args.include_name:
        parser.error("--anonymize-name requires --include-name")

    build_model_dataset(
        input_csv=args.input_csv,
        output_csv=args.output_csv,
        include_name=args.include_name,
        anonymize_name=args.anonymize_name,
        legacy_generation=args.legacy_generation,
        age_col=args.age_col,
        income_col=args.income_col,
        education_col=args.education_col,
        immigrant_col=args.immigrant_col,
        occupation_col=args.occupation_col,
        name_col=args.name_col,
    )


if __name__ == "__main__":
    main()