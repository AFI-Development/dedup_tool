## T03 — Fuzzy, default schema detection

Input rows: 300
Mode: fuzzy
Clean rows: 300
Duplicates found: 0

Finding:
Dataset uses separate First Name and Last Name fields.
Current fuzzy matcher expects a single recognized name field.
Without a name field, maximum weighted score is 0.50, below
the default 0.85 duplicate threshold.

Result:
Identified a column-mapping limitation before Fiverr release.
