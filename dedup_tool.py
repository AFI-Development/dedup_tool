from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None


DEFAULT_NAME_COLUMNS = ["name", "customer", "customer_name", "vendor", "vendor_name", "payee"]
DEFAULT_FIRST_NAME_COLUMNS = ["first_name", "first name", "firstname"]
DEFAULT_LAST_NAME_COLUMNS = ["last_name", "last name", "lastname"]
DEFAULT_EMAIL_COLUMNS = ["email", "email_address", "e-mail"]
DEFAULT_PHONE_COLUMNS = ["phone", "phone_number", "telephone", "mobile"]
DEFAULT_ADDRESS_COLUMNS = ["address", "street", "street_address"]


def normalize_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s@]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_email(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    for ch in text:
        if ch.isspace():
            return ""

    if text.count("@") != 1:
        return ""

    local, domain = text.split("@", 1)

    local_allowed = re.fullmatch(r"[a-z0-9._+-]+", local)
    domain_allowed = re.fullmatch(r"[a-z0-9.-]+", domain)

    if local_allowed is None:
        return ""
    if domain_allowed is None:
        return ""

    if "." not in domain:
        return ""
    if local.startswith("."):
        return ""
    if domain.startswith("."):
        return ""
    if local.endswith("."):
        return ""
    if domain.endswith("."):
        return ""

    split_domain = domain.split(".")

    for domain_label in split_domain:
        allowed_domain = re.fullmatch(r"[a-z0-9-]+", domain_label)
        if allowed_domain is None:
            return ""
        if domain_label.startswith("-"):
            return ""
        if domain_label.endswith("-"):
            return ""

    if ".." in local:
        return ""
    if ".." in domain:
        return ""
    if domain.startswith("-"):
        return ""
    if domain.endswith("-"):
        return ""

    return text

def normalize_phone(value: Any) -> str:
    if pd.isna(value):
        return ""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def normalize_address(value: Any) -> str:
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
    normalized_columns = {
        re.sub(r"[\s-]+", "_", str(c).lower()): c
        for c in columns
    }

    for candidate in candidates:
        normalized_candidate = re.sub(r"[\s-]+", "_", candidate.lower())

        if normalized_candidate in normalized_columns:
            return normalized_columns[normalized_candidate]

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
    if suffix == ".xlsx":
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file type: {suffix}. Use CSV or XLSX.")


def save_file(df: pd.DataFrame, path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path, index=False)
        return
    if suffix == ".xlsx":
        df.to_excel(path, index=False)
        return
    raise ValueError(f"Unsupported output type: {suffix}. Use CSV or XLSX.")


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
    email_score: float,
    phone_match: bool,
    address_match: bool,
) -> float:
    score = 0.0
    score += (name_score / 100.0) * 0.50
    score += email_score
    score += 0.15 if phone_match else 0.0
    score += 0.10 if address_match else 0.0
    return min(score, 1.0)


def build_match_record(
    row: pd.Series,
    matched_row: pd.Series,
    matched_index: int,
    name_score: int,
    email_score: float,
    email_domain_match: bool,
    email_local_score: float,
    weighted_score: float,
    confidence: str,
    email_match: bool,
    phone_match: bool,
    address_match: bool,
    decision: str,
    name_col: str | None,
    first_name_col: str | None,
    last_name_col: str | None,
    email_col: str | None,
    phone_col: str | None,
    address_col: str | None,
) -> dict:
    return {
        "decision": decision,
        "matched_to_index": matched_index,
        "name_similarity_score": name_score,
        "weighted_match_score": round(weighted_score, 4),
        "confidence": confidence,
        "matched_on_email": email_match,
        "matched_on_phone": phone_match,
        "matched_on_address": address_match,
        "email_evidence_score": email_score,
        "email_domain_exact_match": email_domain_match,
        "email_local_similarity_score": email_local_score,
        "candidate_name": row[name_col] if name_col else "",
        "matched_name": matched_row[name_col] if name_col else "",
        "candidate_first_name": row[first_name_col] if first_name_col else "",
        "matched_first_name": matched_row[first_name_col] if first_name_col else "",
        "candidate_last_name": row[last_name_col] if last_name_col else "",
        "matched_last_name": matched_row[last_name_col] if last_name_col else "",
        "candidate_email": row[email_col] if email_col else "",
        "matched_email": matched_row[email_col] if email_col else "",
        "candidate_phone": row[phone_col] if phone_col else "",
        "matched_phone": matched_row[phone_col] if phone_col else "",
        "candidate_address": row[address_col] if address_col else "",
        "matched_address": matched_row[address_col] if address_col else "",
    }

def fuzzy_dedup(
    df: pd.DataFrame,
    name_col: str | None,
    first_name_col: str | None,
    last_name_col: str | None,
    email_col: str | None,
    phone_col: str | None,
    address_col: str | None,
    threshold: float,
    review_threshold: float,
    min_name_score: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    working = df.copy()
    if name_col:
        working["_normalized_name"] = working[name_col].map(normalize_text)

    elif first_name_col and last_name_col:
        working["_normalized_name"] = (
            working[first_name_col].fillna("").astype(str)
            + " "
            + working[last_name_col].fillna("").astype(str)
        ).map(normalize_text)

    else:
        working["_normalized_name"] = ""
    working["_normalized_email"] = working[email_col].map(normalize_email) if email_col else ""
    working["_normalized_phone"] = working[phone_col].map(normalize_phone) if phone_col else ""
    working["_normalized_address"] = working[address_col].map(normalize_address) if address_col else ""

    keep_indices: list[int] = []
    duplicate_rows: list[dict] = []
    review_rows: list[dict] = []

    for idx, row in working.iterrows():
        best_match_index: int | None = None
        best_matched_row: pd.Series | None = None
        best_match_score = 0.0
        best_match_name_score = 0
        best_email_match = False
        best_email_domain_match = False
        best_email_local_score = 0
        best_email_score = 0.0
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
            has_name: bool = bool(
                name_col or (first_name_col and last_name_col)
            )

            name_score = (
                compute_fuzzy_score(
                    row["_normalized_name"],
                    kept_row["_normalized_name"],
                )
                if has_name
                else 0
            )

            email_score = 0.0
            email_domain_match = False
            email_local_score = 0.0

            row_email = str(row["_normalized_email"])
            kept_email = str(kept_row["_normalized_email"])

            if row_email and kept_email:
                row_local = row_email.split("@")[0]
                kept_local = kept_email.split("@")[0]
                row_domain = row_email.split("@")[1]
                kept_domain = kept_email.split("@")[1]

                email_domain_match = bool(
                    row_domain == kept_domain
                )

                email_local_score = compute_fuzzy_score(row_local, kept_local)

                if email_match:
                    email_score = 0.25
                elif email_domain_match and email_local_score >= 95:
                    email_score = 0.20
                elif email_domain_match and email_local_score >= 90:
                    email_score = 0.15
                elif email_domain_match and email_local_score >= 80:
                    email_score = 0.10

            weighted_score = compute_weighted_score(
                name_score=name_score,
                email_score=email_score,
                phone_match=phone_match,
                address_match=address_match,
            )

            if weighted_score > best_match_score:
                best_match_index = kept_idx
                best_matched_row = kept_row
                best_match_score = weighted_score
                best_match_name_score = name_score
                best_email_score = email_score
                best_email_match = email_match
                best_email_domain_match = email_domain_match
                best_email_local_score = email_local_score
                best_phone_match = phone_match
                best_address_match = address_match

        has_name = bool(name_col or (first_name_col and last_name_col))
        minimum_name_score = min_name_score if has_name else 0

        if (
            best_match_index is not None
            and best_matched_row is not None
            and best_match_score >= threshold
            and best_match_name_score >= minimum_name_score
        ):
            record = build_match_record(row=row, matched_row=best_matched_row,
                                        matched_index=best_match_index,
                                        name_score=best_match_name_score,
                                        email_score=best_email_score,
                                        email_domain_match=best_email_domain_match,
                                        email_local_score=best_email_local_score,
                                        weighted_score=best_match_score,
                                        confidence=classify_confidence(best_match_score),
                                        email_match=best_email_match, phone_match=best_phone_match,
                                        address_match=best_address_match, decision="duplicate",
                                        name_col=name_col,first_name_col=first_name_col,
                                        last_name_col=last_name_col, email_col=email_col,
                                        phone_col=phone_col, address_col=address_col)
            duplicate_rows.append(record)

        elif (
            best_match_index is not None
            and best_matched_row is not None
            and best_match_score >= review_threshold
            and best_match_name_score >= minimum_name_score
        ):
            record = build_match_record(row=row, matched_row=best_matched_row,
                                        matched_index=best_match_index,
                                        name_score=best_match_name_score,
                                        email_score=best_email_score,
                                        email_domain_match=best_email_domain_match,
                                        email_local_score=best_email_local_score,
                                        weighted_score=best_match_score,
                                        confidence=classify_confidence(best_match_score),
                                        email_match=best_email_match, phone_match=best_phone_match,
                                        address_match=best_address_match, decision="review",
                                        name_col=name_col, first_name_col=first_name_col,
                                        last_name_col=last_name_col, email_col=email_col,
                                        phone_col=phone_col, address_col=address_col)
            review_rows.append(record)
            keep_indices.append(idx)

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

    review_df = pd.DataFrame(review_rows).drop(
        columns=[
            "_normalized_name",
            "_normalized_email",
            "_normalized_phone",
            "_normalized_address",
        ],
        errors="ignore",
    )

    return cleaned, duplicates, review_df


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
                "decision",
                "candidate_name",
                "matched_name",
                "candidate_email",
                "matched_email",
                "candidate_phone",
                "matched_phone",
                "candidate_address",
                "matched_address",
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
        description="Deduplicate CSV or XLSX data using exact or fuzzy matching."
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
        "--review-threshold",
        type=float,
        default=0.75,
        help="Minimum weighted score for manual review classification",
    )
    parser.add_argument(
        "--output-review",
        default="manual_review.csv",
        help="Path to manual-review output file",
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
    review_path = Path(args.output_review)

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
        review_rows = pd.DataFrame()
    else:
        name_col = first_existing_column(df.columns, DEFAULT_NAME_COLUMNS)
        first_name_col = first_existing_column(df.columns, DEFAULT_FIRST_NAME_COLUMNS)
        last_name_col = first_existing_column(df.columns, DEFAULT_LAST_NAME_COLUMNS)
        email_col = first_existing_column(df.columns, DEFAULT_EMAIL_COLUMNS)
        phone_col = first_existing_column(df.columns, DEFAULT_PHONE_COLUMNS)
        address_col = first_existing_column(df.columns, DEFAULT_ADDRESS_COLUMNS)

        if not any([name_col, first_name_col, last_name_col, phone_col, address_col]):
            print(
                "Fuzzy mode could not find likely matching columns. "
                "Add columns like name, email, phone, or address.",
                file=sys.stderr,
            )
            return 1

        cleaned, duplicates, review_rows = fuzzy_dedup(
            df=df,
            name_col=name_col,
            first_name_col=first_name_col,
            last_name_col=last_name_col,
            email_col=email_col,
            phone_col=phone_col,
            address_col=address_col,
            threshold=args.threshold,
            review_threshold=args.review_threshold,
            min_name_score=args.min_name_score,
        )

    try:
        save_file(cleaned, clean_path)
        save_file(duplicates, duplicates_path)
        save_file(review_rows, review_path)
    except Exception as exc:
        print(f"Could not save output: {exc}", file=sys.stderr)
        return 1

    print("\nDone.")
    print("--- RESULTS ---")
    print(f"Original rows:        {len(df):,}")
    print(f"Clean output rows:    {len(cleaned):,}")
    print(f"Duplicates removed:   {len(duplicates):,}")
    print(f"Manual review rows:   {len(review_rows):,}")
    print(f"Total flagged:        {len(duplicates) + len(review_rows):,}")

    print("\n--- OUTPUT FILES ---")
    print(f"Clean file:           {clean_path}")
    print(f"Duplicates file:      {duplicates_path}")
    print(f"Manual review file:   {review_path}")

    if args.mode == "fuzzy":
        print("\n--- MATCH SETTINGS ---")
        print(f"Duplicate threshold:  {args.threshold:.2f}")
        print(f"Review threshold:     {args.review_threshold:.2f}")
        print(f"Minimum name score:   {args.min_name_score}")

    if args.debug:
        print_debug_preview(cleaned, duplicates, args.preview_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())