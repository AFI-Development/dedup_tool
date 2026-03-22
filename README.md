# README.md

### Fuzzy deduplication

```bash
python dedup_tool.py input.csv --mode fuzzy --threshold 90
```

---

## Input Formats

- CSV (.csv)
- Excel (.xlsx, .xls)

---

## Output

- `cleaned_output.csv` → deduplicated data
- `duplicates_review.csv` → flagged duplicates

---

## Example

Input:

```
John Smith,john@gmail.com
J Smith,john@gmail.com
```

Output:

- One clean record
- One duplicate flagged

---

## Notes

- Fuzzy matching requires `rapidfuzz`
- Threshold controls how strict matching is (0–100)

---

## Next Improvements (Planned)

- Confidence scoring
- Better business/vendor normalization
- Interactive review mode
- Batch processing

---

## Author


