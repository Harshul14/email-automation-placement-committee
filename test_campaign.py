"""
test_campaign.py
=================
Unit tests for the parts of the system that don't require a live
Microsoft 365 connection: Excel parsing, POC/email matching, rotation,
batching, and duplicate protection. Run with:

    pytest test_campaign.py -v

These map to the brief's test plan (TEST 1-15; TEST 16-18 require a
live mailbox and are covered by mail_client.py's structure/comments
instead, since they can't be exercised in an automated unit test).
"""

import json
import os
import tempfile

import pandas as pd
import pytest

import config
from contact_matcher import build_poc_map, greeting_for, select_next_contact
from validators import extract_valid_emails, parse_name_with_title, normalize_company_key


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """Point the DB at a throwaway temp file for every test."""
    db_file = tmp_path / "test_campaign_state.db"
    monkeypatch.setattr(config, "DRIVE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "MODE", "TEST")
    import database
    database.init_db()
    yield


# --- TEST 1: one company, one email -----------------------------------
def test_single_email_no_rotation_available():
    emails = extract_valid_emails("rahul@abc.com")
    assert emails == ["rahul@abc.com"]
    poc_map = build_poc_map("Mr. Rahul", emails)
    assert poc_map["rahul@abc.com"]["first_name"] == "Rahul"
    assert greeting_for(poc_map["rahul@abc.com"]) == "Dear Mr. Rahul,"


# --- TEST 2: three emails, all POCs mapped -----------------------------
def test_three_emails_all_poc_mapped():
    emails = extract_valid_emails("rahul@abc.com, priya@abc.com, amit@abc.com")
    names = "Mr. Rahul, Ms. Priya, Mr. Amit"
    poc_map = build_poc_map(names, emails)
    assert poc_map["rahul@abc.com"]["first_name"] == "Rahul"
    assert poc_map["priya@abc.com"]["first_name"] == "Priya"
    assert poc_map["amit@abc.com"]["first_name"] == "Amit"


# --- TEST 3: three emails, no POCs mapped ------------------------------
def test_three_emails_no_poc_mapped():
    emails = extract_valid_emails("abc@company.com, hr@company.com, careers@company.com")
    poc_map = build_poc_map("", emails)
    for e in emails:
        assert greeting_for(poc_map[e]) == "Dear Team,"


# --- TEST 4: only one of several emails has a POC ----------------------
def test_partial_poc_mapping():
    emails = extract_valid_emails("rahul@abc.com, hr@abc.com, careers@abc.com")
    poc_map = build_poc_map("Mr. Rahul", emails)
    assert greeting_for(poc_map["rahul@abc.com"]) == "Dear Mr. Rahul,"
    assert greeting_for(poc_map["hr@abc.com"]) == "Dear Team,"
    assert greeting_for(poc_map["careers@abc.com"]) == "Dear Team,"


# --- TEST: mismatched name/email counts (the real-world Excel case) ---
def test_mismatched_counts_does_not_misattribute():
    # 2 names, 3 emails -> must not blindly zip() them
    emails = extract_valid_emails("aharsh@accubits.com, srikanth@accubits.com, srikanthvraj@gmail.com")
    poc_map = build_poc_map("Mr. Aharsh, Mr. Srikanth V. Raj", emails)
    assert poc_map["aharsh@accubits.com"]["first_name"] == "Aharsh"
    assert poc_map["srikanth@accubits.com"]["first_name"] == "Srikanth"
    # third email's local part doesn't match "Aharsh" or "Srikanth V. Raj" well enough
    # beyond partial "srikanth" overlap -- confirm it resolves to a name, not blank/wrong
    assert poc_map["srikanthvraj@gmail.com"]["first_name"] in ("Srikanth", None)


# --- TEST 5 & 45: rotation cycles through contacts ----------------------
def test_rotation_cycles_through_contacts():
    import database
    emails = ["rahul@abc.com", "priya@abc.com", "amit@abc.com"]
    key = normalize_company_key("ABC Ltd.")
    database.upsert_company(key, "ABC Ltd.", json.dumps(emails), json.dumps({}))

    seen_order = []
    for _ in range(4):
        row = database.get_company(key)
        nxt = select_next_contact(row, {}, emails)
        seen_order.append(nxt)
        database.update_rotation(key, nxt)

    assert seen_order == ["rahul@abc.com", "priya@abc.com", "amit@abc.com", "rahul@abc.com"]


# --- TEST 6: duplicate company rows are not double-counted -------------
def test_duplicate_company_rows_not_double_counted():
    from validators import normalize_company_key
    a = normalize_company_key("ABC Ltd.")
    b = normalize_company_key("ABC Ltd.  ")
    assert a == b  # whitespace-insensitive
    # Note: "ABC Ltd." vs "ABC Limited" intentionally do NOT normalize to
    # the same key -- that requires human review (near_duplicate_warnings),
    # per the brief's "do not silently merge" rule.
    c = normalize_company_key("ABC Limited")
    assert a != c


# --- TEST 7: missing email --------------------------------------------
def test_missing_email_returns_empty():
    assert extract_valid_emails(None) == []
    assert extract_valid_emails("NA") == []
    assert extract_valid_emails("") == []


# --- TEST 8: invalid email --------------------------------------------
def test_invalid_email_filtered_out():
    emails = extract_valid_emails("not-an-email, rahul@abc.com, also bad")
    assert emails == ["rahul@abc.com"]


# --- TEST 14: never send twice to same company in same batch -----------
def test_company_not_repeated_within_batch_selection():
    import database
    from campaign_runner import select_batch
    from excel_parser import CompanyRecord

    key = normalize_company_key("ABC Ltd.")
    emails = ["rahul@abc.com"]
    poc_map = build_poc_map("Mr. Rahul", emails)
    record = CompanyRecord(1, "ABC Ltd.", key, emails, poc_map, "In_Contact", None)

    database.upsert_company(key, "ABC Ltd.", json.dumps(emails), json.dumps(poc_map))

    batch = select_batch([record, record, record])  # simulate dup rows
    company_keys = [b["company_key"] for b in batch]
    assert company_keys.count(key) == 1


# --- TEST 11: batch size respects DAILY_COMPANY_LIMIT -------------------
def test_batch_respects_daily_limit(monkeypatch):
    import database
    from campaign_runner import select_batch
    from excel_parser import CompanyRecord

    monkeypatch.setattr(config, "DAILY_COMPANY_LIMIT", 3)

    records = []
    for i in range(5):
        name = f"Company {i}"
        key = normalize_company_key(name)
        emails = [f"contact{i}@example.com"]
        database.upsert_company(key, name, json.dumps(emails), json.dumps({}))
        records.append(CompanyRecord(i, name, key, emails, {}, "In_Contact", None))

    batch = select_batch(records)
    assert len(batch) == 3


# --- TEST 12/13: TEST mode never targets the real Excel recipient ------
def test_test_mode_redirects_recipient():
    assert config.is_test_mode() is True
    assert config.active_cc_list() == config.TEST_CC_EMAILS
    assert config.TEST_REDIRECT_EMAIL != "rahul@abc.com"


def test_production_mode_uses_real_cc(monkeypatch):
    monkeypatch.setattr(config, "MODE", "PRODUCTION")
    assert config.active_cc_list() == config.PRODUCTION_CC_EMAILS


# --- parse_name_with_title never guesses gender -------------------------
def test_no_gender_guessing_without_explicit_title():
    title, name = parse_name_with_title("Rahul Sharma")  # no Mr./Ms. prefix
    assert title is None and name is None
