"""
contact_matcher.py
===================
Solves the core ambiguity in this Excel: 'Contact Person' and 'Email Id'
are both comma-separated lists, but their counts frequently DON'T match
(e.g. 2 names but 3 emails), so a naive index-based zip() would silently
attribute the wrong person to the wrong email.

Approach (same idea as your earlier recruiter-outreach project's
RapidFuzz-based POC detection): for each email address, fuzzy-match its
local-part against every candidate name. If the best match clears
FUZZY_MATCH_THRESHOLD, that email is confidently mapped to that person
(title + first name, both taken directly from the Excel — never
inferred). If nothing clears the bar, that email has NO POC mapping and
must greet with "Dear Team," per the brief's explicit rule against
guessing.
"""

import re

from rapidfuzz import fuzz

import config
from validators import parse_name_with_title


def _local_part_tokens(email):
    local = email.split("@")[0]
    # split camel/dot/underscore/digit-separated local parts into tokens
    local = re.sub(r"[._\-0-9]+", " ", local)
    return local.strip()


def build_poc_map(contact_person_cell, email_list):
    """
    Returns: dict {email: {"title": "Mr"/"Ms"/None, "first_name": str/None}}
    Every email in email_list gets an entry; unmatched emails map to
    title=None, first_name=None (renderer treats this as "Dear Team,").
    """
    from validators import split_multi_value

    raw_names = split_multi_value(contact_person_cell)
    candidates = []  # list of (title, first_name, full_name_text)
    for raw in raw_names:
        title, first_name = parse_name_with_title(raw)
        if title and first_name:
            candidates.append((title, first_name, raw.replace("\xa0", " ").strip()))

    poc_map = {}
    used_candidate_idx = set()

    for email in email_list:
        local_text = _local_part_tokens(email)
        best_score = 0
        best_idx = None
        for idx, (title, first_name, full_name) in enumerate(candidates):
            score = fuzz.partial_ratio(local_text.lower(), full_name.lower())
            # Also reward a direct first-name-in-local-part hit strongly
            if first_name.lower() in local_text.lower():
                score = max(score, 95)
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is not None and best_score >= config.FUZZY_MATCH_THRESHOLD:
            title, first_name, _ = candidates[best_idx]
            poc_map[email] = {"title": title, "first_name": first_name, "confidence": best_score}
            used_candidate_idx.add(best_idx)
        else:
            poc_map[email] = {"title": None, "first_name": None, "confidence": best_score}

    return poc_map


def greeting_for(poc_entry):
    """Build the exact salutation line for a given poc_map entry."""
    if poc_entry and poc_entry.get("title") and poc_entry.get("first_name"):
        return f"Dear {poc_entry['title']}. {poc_entry['first_name']},"
    return "Dear Team,"


def select_next_contact(company_row, poc_map, all_emails):
    """
    Rotation logic: given the company's DB row (last_contacted_email,
    rotation_index) and the current list of valid emails, pick the next
    email in round-robin order, skipping ones contacted most recently.
    If the company has never been contacted, start at the first email.
    If all contacts have been cycled through, restart from the top.
    """
    if not all_emails:
        return None

    if not company_row or not company_row.get("last_contacted_email"):
        return all_emails[0]

    last_email = company_row["last_contacted_email"]
    if last_email in all_emails:
        last_idx = all_emails.index(last_email)
        next_idx = (last_idx + 1) % len(all_emails)
        return all_emails[next_idx]

    # last contacted email no longer in the current valid list (e.g. Excel
    # updated) -> just start from the top of the current list
    return all_emails[0]
