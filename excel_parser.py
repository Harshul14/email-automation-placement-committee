"""
excel_parser.py
================
Reads the 'DB' sheet of the recruiter Excel file, validates each row,
and produces normalized company records. The 'Details' sheet is a
reference/legend tab (dropdown values) and is intentionally ignored.

This module does NOT assume column positions — it looks columns up by
their exact header names, as inspected from the actual file:
Sr. No., Company Name, Sector, Sub-Sector, Owner, Location,
Contact Person, Designation, Contact Mobile, Landline, Email Id,
Owners comments, Client Priority, Status, Engagement Focus, JD Details,
Date of First Contact, Date of Follow Up, Date of Next Contact,
Remarks (if any)
"""

from difflib import SequenceMatcher

import pandas as pd

import config
from contact_matcher import build_poc_map
from validators import extract_valid_emails, normalize_company_key
from logger_setup import get_logger

logger = get_logger()

REQUIRED_COLUMNS = ["Company Name", "Contact Person", "Email Id", "Owner"]


class CompanyRecord:
    def __init__(self, sr_no, company_name, company_key, emails, poc_map, status, comments):
        self.sr_no = sr_no
        self.company_name = company_name
        self.company_key = company_key
        self.emails = emails            # list[str], valid & deduped
        self.poc_map = poc_map          # dict email -> {title, first_name, confidence}
        self.status = status
        self.comments = comments


def load_companies(excel_path, sheet_name=None, owner_filter=None):
    """
    Returns (records, skipped) where records is a list[CompanyRecord] and
    skipped is a list of (sr_no, company_name, reason) for rows excluded
    due to missing/invalid data.
    """
    sheet_name = sheet_name or config.EXCEL_SHEET
    df = pd.read_excel(excel_path, sheet_name=sheet_name)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Excel is missing required columns: {missing_cols}. "
            f"Found columns: {list(df.columns)}"
        )

    records = []
    skipped = []
    seen_keys = {}  # company_key -> company_name, for near-duplicate detection

    for _, row in df.iterrows():
        sr_no = row.get("Sr. No.")
        company_name = row.get("Company Name")
        owner = row.get("Owner")

        if owner_filter and (pd.isna(owner) or str(owner).strip() != owner_filter):
            continue  # not this owner's row — not a skip, just not in scope

        if pd.isna(company_name) or not str(company_name).strip():
            skipped.append((sr_no, company_name, "missing company name"))
            continue

        company_name = str(company_name).strip()
        company_key = normalize_company_key(company_name)

        emails = extract_valid_emails(row.get("Email Id"))
        if not emails:
            skipped.append((sr_no, company_name, "no valid email address"))
            continue

        poc_map = build_poc_map(row.get("Contact Person"), emails)

        status = None if pd.isna(row.get("Status")) else str(row.get("Status")).strip()
        comments = None if pd.isna(row.get("Owners comments")) else str(row.get("Owners comments")).strip()

        record = CompanyRecord(sr_no, company_name, company_key, emails, poc_map, status, comments)
        records.append(record)

        # near-duplicate warning (do NOT auto-merge — just flag for review)
        for other_key, other_name in seen_keys.items():
            similarity = SequenceMatcher(None, company_key, other_key).ratio()
            if similarity >= 0.90 and company_key != other_key:
                logger.info(
                    f"Possible near-duplicate company names: "
                    f"'{company_name}' vs '{other_name}' (similarity={similarity:.2f})"
                )
                import database
                database.record_near_duplicate(company_name, other_name, similarity)
        seen_keys[company_key] = company_name

    logger.info(
        f"Excel parsed: {len(records)} valid companies, {len(skipped)} skipped."
    )
    for sr_no, name, reason in skipped:
        logger.info(f"SKIPPED row Sr.No={sr_no} company={name!r}: {reason}")

    return records, skipped
