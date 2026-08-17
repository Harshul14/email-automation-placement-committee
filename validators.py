"""
validators.py
=============
Small, dependency-free validation helpers used throughout the pipeline.
"""

import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# Values seen in the Excel that mean "no real email" — must be filtered out
INVALID_EMAIL_TOKENS = {"na", "n/a", "nan", "none", "-", ""}

SEPARATOR_RE = re.compile(r"[,;/\n]+")


def split_multi_value(raw):
    """Split a comma/semicolon/slash/newline-separated Excel cell into a
    clean list of trimmed, non-empty strings. Handles stray whitespace
    and non-breaking spaces."""
    if raw is None:
        return []
    text = str(raw).replace("\xa0", " ").strip()
    if not text or text.lower() in INVALID_EMAIL_TOKENS:
        return []
    parts = [p.strip() for p in SEPARATOR_RE.split(text)]
    return [p for p in parts if p]


def is_valid_email(value):
    if not value:
        return False
    v = value.strip().lower()
    if v in INVALID_EMAIL_TOKENS:
        return False
    return bool(EMAIL_RE.match(v))


def extract_valid_emails(raw_cell):
    """Given a raw Excel 'Email Id' cell (possibly multiple addresses,
    possibly containing junk like 'NA'), return only the valid, deduped,
    lower-cased addresses, preserving first-seen order."""
    candidates = split_multi_value(raw_cell)
    seen = set()
    result = []
    for c in candidates:
        c_clean = c.strip().strip(",").lower()
        if is_valid_email(c_clean) and c_clean not in seen:
            seen.add(c_clean)
            result.append(c_clean)
    return result


TITLE_RE = re.compile(r"^(Mr\.?|Ms\.?|Mrs\.?)\s+(.*)$", re.IGNORECASE)


def parse_name_with_title(raw_name):
    """Given something like 'Mr. Aharsh' or 'Ms. Amrutha Jagdish', return
    (title, first_name) e.g. ('Mr', 'Aharsh'). If no explicit Mr./Ms.
    prefix is present, title is None (caller must fall back to 'Dear
    Team' rather than guessing gender)."""
    if not raw_name:
        return None, None
    text = raw_name.replace("\xa0", " ").strip()
    m = TITLE_RE.match(text)
    if not m:
        return None, None
    title_raw = m.group(1).rstrip(".")
    rest = m.group(2).strip()
    if not rest:
        return None, None
    first_name = rest.split()[0].strip(",")
    title = "Mr" if title_raw.lower() == "mr" else "Ms"  # Mrs -> Ms per brief's Mr/Ms rule
    return title, first_name


def normalize_company_key(company_name):
    """Normalize a company name into a stable lookup key. Deliberately
    conservative: lowercases and collapses whitespace/punctuation, but
    does NOT strip legal suffixes (Pvt Ltd, LLC, etc.) or otherwise try
    to merge names — per the brief, we don't auto-merge without strong
    evidence. Near-duplicate detection is a separate, explicit step."""
    if not company_name:
        return ""
    text = str(company_name).replace("\xa0", " ").strip().lower()
    text = re.sub(r"[^\w\s]", "", text)   # strip punctuation
    text = re.sub(r"\s+", " ", text)      # collapse whitespace
    return text
