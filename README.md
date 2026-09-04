# Dedup Tool

**Version 0.1.0 — Early usable release**

A command-line Python tool for deduplicating CSV and XLSX datasets using exact and fuzzy matching.

Fuzzy mode combines normalized name similarity with email, phone, and address signals, then separates higher-confidence duplicates from records that should be reviewed manually.

## Features

- Exact duplicate removal
- Fuzzy matching with `rapidfuzz`
- Weighted scoring across name, email, phone, and address
- Support for either a full-name column or separate first/last-name columns
- Confidence classification
- Manual-review output for ambiguous matches
- Run summary showing original, clean, duplicate, review, and total-flagged counts
- CSV and XLSX input support
- CSV or XLSX output support

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Exact deduplication

```bash
python dedup_tool.py input.csv --mode exact
```

To limit exact matching to selected columns:

```bash
python dedup_tool.py input.csv --mode exact --columns name email phone
```

### Fuzzy deduplication

```bash
python dedup_tool.py input.csv --mode fuzzy
```

The default fuzzy settings are intentionally conservative:

- Duplicate threshold: `0.85`
- Manual-review threshold: `0.75`
- Minimum fuzzy name score: `70`

These values can be adjusted from the command line:

```bash
python dedup_tool.py input.csv --mode fuzzy --threshold 0.90 --review-threshold 0.75 --min-name-score 75
```

Thresholds are rule-based and may need tuning for different datasets or industries. Lower thresholds increase recall but can also increase false positives, so review results before using more permissive settings in production.

## Input Formats

- CSV (`.csv`)
- Excel (`.xlsx`)

## Recognized Matching Columns

Fuzzy mode attempts to detect commonly named fields for:

- full name
- first name + last name
- email
- phone
- address

Column-name matching is normalized so common variations such as spaces, hyphens, and underscores can map to the same logical field. For example, `Phone Number` can match a configured `phone_number` candidate.

## Output

By default, the tool creates:

- `cleaned_output.csv` — records retained after automatic duplicate removal
- `duplicates_review.csv` — records classified as duplicates
- `manual_review.csv` — ambiguous records requiring manual review

Custom output paths can be supplied with `--output-clean`, `--output-duplicates`, and `--output-review`.

At the end of each run, the CLI prints a summary similar to:

```text
--- RESULTS ---
Original rows:        300
Clean output rows:    236
Duplicates removed:    64
Manual review rows:     4
Total flagged:          68
```

In fuzzy mode, the active duplicate threshold, review threshold, and minimum name score are also printed so the run can be reproduced later.

Manual-review rows remain in the cleaned output because they have not been automatically removed.

## Demo and Test Fixtures

Small synthetic datasets may be included under `tests/` to support reproducible demonstrations and validation.

The real-estate demo fixture is intended to exercise:

- exact duplicates
- case and whitespace normalization
- phone-number formatting differences
- address variations
- name and email typos
- company-name abbreviation or punctuation differences
- missing fields
- multi-field fuzzy matches

Ground-truth files may be stored alongside demo inputs so matching results can be checked against known duplicate relationships.

Generated run outputs are normally ignored unless they are intentionally preserved as documented regression fixtures.

### Validated demo calibration

A documented 300-row synthetic real-estate fixture has also been tested with a more permissive calibration:

```text
Duplicate threshold: 0.75
Review threshold:    0.60
Minimum name score:  70
```

That calibration is useful as a regression/demo profile for the fixture, but it is not the global default and should not be assumed appropriate for every dataset.

## Fuzzy Matching

Fuzzy mode normalizes common name, email, phone, and address fields before comparing records.

The weighted score currently uses:

- Name similarity: 50%
- Email evidence: up to 25%
- Exact normalized phone match: 15%
- Exact normalized address match: 10%

Email evidence is hierarchical rather than additive. An exact normalized email receives the strongest email score, while same-domain local-part similarity may receive a lower partial score.

When a usable name source is available, a record must also meet the configured minimum fuzzy name score before it can be classified as a duplicate or manual-review candidate.

## Debug Preview

Use `--debug` to print a small preview of cleaned and duplicate records:

```bash
python dedup_tool.py input.csv --mode fuzzy --debug
```

The number of preview rows can be changed with `--preview-rows`.

## Current Limitations

Version 0.1.0 is an early usable release. Matching weights and thresholds are currently rule-based and may need tuning for different datasets or industries.

Fuzzy matching currently compares records iteratively against retained records, so very large datasets may require additional candidate blocking or performance optimization.

Matching is order-dependent because fuzzy candidates are compared against records retained earlier in the dataset.

Legacy `.xls` files are not supported in this release; convert them to `.xlsx` or `.csv` first.

## Planned Improvements

- Configurable field weights
- Improved business and vendor normalization
- Better candidate blocking for larger datasets
- Expanded testing and benchmark datasets
- More flexible column mapping
- Additional review and reporting options
- Named matching profiles or configuration files for repeatable calibrations

## Requirements

- Python 3.10+
- pandas
- rapidfuzz
- openpyxl

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
