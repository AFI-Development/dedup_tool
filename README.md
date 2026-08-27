# Dedup Tool

**Version 0.1.0 — Early usable release**

A command-line Python tool for deduplicating CSV and Excel datasets using exact and fuzzy matching.

Fuzzy mode combines normalized name similarity with email, phone, and address signals, then separates high-confidence duplicates from records that should be reviewed manually.

## Features

- Exact duplicate removal
- Fuzzy matching with `rapidfuzz`
- Weighted scoring across name, email, phone, and address
- Confidence classification
- Manual-review output for ambiguous matches
- CSV and Excel input support
- CSV or Excel output support

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

The default fuzzy settings are:

- Duplicate threshold: `0.85`
- Manual-review threshold: `0.75`
- Minimum fuzzy name score: `70`

These values can be adjusted from the command line:

```bash
python dedup_tool.py input.csv --mode fuzzy --threshold 0.90 --review-threshold 0.75 --min-name-score 75
```

## Input Formats

- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)

## Output

By default, the tool creates:

- `cleaned_output.csv` — deduplicated records
- `duplicates_review.csv` — records classified as duplicates
- `manual_review.csv` — ambiguous records requiring manual review

Custom output paths can be supplied with `--output-clean`, `--output-duplicates`, and `--output-review`.

## Fuzzy Matching

Fuzzy mode normalizes common name, email, phone, and address fields before comparing records.

The weighted score currently uses:

- Name similarity: 50%
- Exact normalized email match: 25%
- Exact normalized phone match: 15%
- Exact normalized address match: 10%

A record must also meet the configured minimum name score when a name column is available.

## Debug Preview

Use `--debug` to print a small preview of cleaned and duplicate records:

```bash
python dedup_tool.py input.csv --mode fuzzy --debug
```

The number of preview rows can be changed with `--preview-rows`.

## Current Limitations

Version 0.1.0 is an early usable release. Matching weights and thresholds are currently rule-based and may need tuning for different datasets or industries.

Large datasets may require additional performance optimization because fuzzy matching currently compares candidate records iteratively.

## Planned Improvements

- Configurable field weights
- Improved business and vendor normalization
- Better candidate blocking for larger datasets
- Expanded testing and benchmark datasets
- More flexible column mapping
- Additional review and reporting options

## Requirements

- Python 3.10+
- pandas
- rapidfuzz
- openpyxl

## License

No license has been specified yet.
