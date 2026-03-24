from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None


DEFAULT_NAME_COLUMNS = ["name", "customer", "customer_name", "vendor", "vendor_name", "payee"]
DEFAULT_EMAIL_COLUMNS = ["email", "email_address", "e-mail"]
DEFAULT_PHONE_COLUMNS = ["phone", "phone_number", "telephone", "mobile"]
DEFAULT_ADDRESS_COLUMNS = ["address", "street", "street_address"]


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s@]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_email(value: object) -> str:
    return normalize_text(value)


def normalize_phone(value: object) -> str:
    if pd.isna(value):
        return ""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def normalize_address(value: object) -> str:
    text = normalize_text(value)
    replacements = {
        " street": " st",
        " avenue": " ave",
        " road": " rd",
        " drive": " dr",
        " lane": " ln",
        " boulevard": " blvd",
        " apartment": " apt",
        " suite": " ste",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def first_existing_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def compute_fuzzy_score(left: str, right: str) -> int:
    if not left or not right:
        return 0
    if fuzz is None:
        raise RuntimeError("rapidfuzz is not installed. Install it with: pip install rapidfuzz")
    return int(fuzz.token_sort_ratio(left, right))


def load_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file type: {suffix}. Use CSV or Excel.")


def save_file(df: pd.DataFrame, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path, index=False)
        return
    if suffix in {".xlsx", ".xls"}:
        df.to_excel(path, index=False)
        return
    raise ValueError(f"Unsupported output type: {suffix}. Use CSV or Excel.")


def exact_dedup(df: pd.DataFrame, subset: list[str] | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    duplicate_mask = df.duplicated(subset=subset, keep="first")
    duplicates = df.loc[duplicate_mask].copy()
    cleaned = df.loc[~duplicate_mask].copy()
    return cleaned, duplicates


def classify_confidence(score: float) -> str:
    if score >= 0.90:
        return "high"
    if score >= 0.75:
        return "medium"
    return "low"


def compute_weighted_score(
    name_score: int,
    email_match: bool,
    phone_match: bool,
    address_match: bool,
) -> float:
    score = 0.0
    score += (name_score / 100.0) * 0.50
    score += 0.25 if email_match else 0.0
    score += 0.15 if phone_match else 0.0
    score += 0.10 if address_match else 0.0
    return min(score, 1.0)


def fuzzy_dedup(
    df: pd.DataFrame,
    name_col: str | None,
    email_col: str | None,
    phone_col: str | None,
    address_col: str | None,
    threshold: float,
    min_name_score: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    working = df.copy()
    working["_normalized_name"] = working[name_col].map(normalize_text) if name_col else ""
    working["_normalized_email"] = working[email_col].map(normalize_email) if email_col else ""
    working["_normalized_phone"] = working[phone_col].map(normalize_phone) if phone_col else ""
    working["_normalized_address"] = working[address_col].map(normalize_address) if address_col else ""

    keep_indices: list[int] = []
    duplicate_rows: list[dict] = []

    for idx, row in working.iterrows():
        best_match_index: int | None = None
        best_match_score = 0.0
        best_match_name_score = 0
        best_email_match = False
        best_phone_match = False
        best_address_match = False

        for kept_idx in keep_indices:
            kept_row = working.loc[kept_idx]

            email_match = bool(
                row["_normalized_email"]
                and row["_normalized_email"] == kept_row["_normalized_email"]
            )
            phone_match = bool(
                row["_normalized_phone"]
                and row["_normalized_phone"] == kept_row["_normalized_phone"]
            )
            address_match = bool(
                row["_normalized_address"]
                and row["_normalized_address"] == kept_row["_normalized_address"]
            )

            name_score = (
                compute_fuzzy_score(row["_normalized_name"], kept_row["_normalized_name"])
                if name_col
                else 0
            )

            weighted_score = compute_weighted_score(
                name_score=name_score,
                email_match=email_match,
                phone_match=phone_match,
                address_match=address_match,
            )

            if weighted_score > best_match_score:
                best_match_index = kept_idx
                best_match_score = weighted_score
                best_match_name_score = name_score
                best_email_match = email_match
                best_phone_match = phone_match
                best_address_match = address_match

        minimum_name_score = min_name_score if name_col else 0

        if (
	    best_match_index is not None
	    and best_match_score >= threshold
	    and best_match_name_score >= minimum_name_score
        ):
            merged = row.to_dict()
            merged["matched_to_index"] = best_match_index
            merged["name_similarity_score"] = best_match_name_score
            merged["weighted_match_score"] = round(best_match_score, 4)
            merged["confidence"] = classify_confidence(best_match_score)
            merged["matched_on_email"] = best_email_match
            merged["matched_on_phone"] = best_phone_match
            merged["matched_on_address"] = best_address_match
            duplicate_rows.append(merged)
        else:
            keep_indices.append(idx)

    cleaned = working.loc[keep_indices].drop(
        columns=[
            "_normalized_name",
            "_normalized_email",
            "_normalized_phone",
            "_normalized_address",
        ],
        errors="ignore",
    )

    duplicates = pd.DataFrame(duplicate_rows).drop(
        columns=[
            "_normalized_name",
            "_normalized_email",
            "_normalized_phone",
            "_normalized_address",
        ],
        errors="ignore",
    )

    return cleaned, duplicates


def print_debug_preview(cleaned: pd.DataFrame, duplicates: pd.DataFrame, limit: int) -> None:
    print("\n--- SAMPLE CLEANED DATA ---")
    if cleaned.empty:
        print("No clean rows to preview.")
    else:
        print(cleaned.head(limit).to_string(index=False))

    print("\n--- SAMPLE DUPLICATES ---")
    if duplicates.empty:
        print("No duplicate rows to preview.")
    else:
        preferred_columns = [
            col
            for col in [
                "name",
                "email",
                "phone",
                "address",
                "matched_to_index",
                "name_similarity_score",
                "weighted_match_score",
                "confidence",
                "matched_on_email",
                "matched_on_phone",
                "matched_on_address",
            ]
            if col in duplicates.columns
        ]
        preview_df = duplicates[preferred_columns] if preferred_columns else duplicates
        print(preview_df.head(limit).to_string(index=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deduplicate CSV or Excel data using exact or fuzzy matching."
    )
    parser.add_argument("input_file", help="Path to input CSV/XLSX file")
    parser.add_argument(
        "--output-clean",
        default="cleaned_output.csv",
        help="Path to cleaned output file",
    )
    parser.add_argument(
        "--output-duplicates",
        default="duplicates_review.csv",
        help="Path to duplicate-review output file",
    )
    parser.add_argument(
        "--mode",
        choices=["exact", "fuzzy"],
        default="exact",
        help="Matching mode",
    )
    parser.add_argument(
        "--columns",
        nargs="*",
        default=None,
        help="Columns to use for exact deduplication",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Fuzzy weighted threshold from 0.0 to 1.0",
    )
    parser.add_argument(
         "--min-name-score",
         type=int,
         default=70,
         help="Minimum fuzzy name score required for fuzzy duplicate classification",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print a small preview of cleaned and duplicate rows to terminal",
    )
    parser.add_argument(
        "--preview-rows",
        type=int,
        default=5,
        help="Number of preview rows to show when using --debug",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input_file)
    clean_path = Path(args.output_clean)
    duplicates_path = Path(args.output_duplicates)

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        df = load_file(input_path)
    except Exception as exc:
        print(f"Could not load file: {exc}", file=sys.stderr)
        return 1

    if df.empty:
        print("Input file is empty.", file=sys.stderr)
        return 1

    if args.mode == "exact":
        subset = args.columns if args.columns else None
        cleaned, duplicates = exact_dedup(df, subset=subset)
    else:
        name_col = first_existing_column(df.columns, DEFAULT_NAME_COLUMNS)
        email_col = first_existing_column(df.columns, DEFAULT_EMAIL_COLUMNS)
        phone_col = first_existing_column(df.columns, DEFAULT_PHONE_COLUMNS)
        address_col = first_existing_column(df.columns, DEFAULT_ADDRESS_COLUMNS)

        if not any([name_col, email_col, phone_col, address_col]):
            print(
                "Fuzzy mode could not find likely matching columns. "
                "Add columns like name, email, phone, or address.",
                file=sys.stderr,
            )
            return 1

        cleaned, duplicates = fuzzy_dedup(
            df=df,
            name_col=name_col,
            email_col=email_col,
            phone_col=phone_col,
            address_col=address_col,
            threshold=args.threshold,
            min_name_score=args.min_name_score,
        )

    try:
        save_file(cleaned, clean_path)
        save_file(duplicates, duplicates_path)
    except Exception as exc:
        print(f"Could not save output: {exc}", file=sys.stderr)
        return 1

    print("Done.")
    print(f"Original rows:   {len(df):,}")
    print(f"Clean rows:      {len(cleaned):,}")
    print(f"Duplicates rows: {len(duplicates):,}")
    print(f"Saved clean file to: {clean_path}")
    print(f"Saved duplicates review file to: {duplicates_path}")

    if args.debug:
        print_debug_preview(cleaned, duplicates, args.preview_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
