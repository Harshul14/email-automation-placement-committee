"""
database.py
============
SQLite persistence layer. Auto-creates the database and schema on first
run — you never create it manually. TEST and PRODUCTION modes point at
separate database files (see config.db_path()), so testing can never
corrupt production campaign history.

Status model (adapted from the original brief — see README for why
SCHEDULED/SCHEDULING don't apply the way they would with Graph API):

    PENDING        -> selected for a batch, nothing done yet
    GENERATED      -> personalized email content built & validated
    DRAFT_CREATED  -> IMAP APPEND to Outlook Drafts succeeded (verified)
    SENT           -> SMTP send succeeded, after explicit user confirmation
    DRAFT          -> draft exists in Outlook but was NOT sent
                       (user declined at confirmation, or send failed)
    FAILED         -> an operation failed before a draft could be created
    SKIPPED        -> row excluded during validation (bad data)
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    company_key         TEXT PRIMARY KEY,   -- normalized company name
    company_name        TEXT NOT NULL,      -- original display name
    all_emails          TEXT NOT NULL,      -- JSON list of all known emails
    poc_map             TEXT NOT NULL,      -- JSON: {email: {"first_name":..., "title":...}}
    last_contacted_email TEXT,
    rotation_index      INTEGER DEFAULT 0,
    times_contacted      INTEGER DEFAULT 0,
    last_campaign_date  TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_key         TEXT NOT NULL,
    company_name        TEXT NOT NULL,
    recipient_email      TEXT NOT NULL,
    poc_first_name       TEXT,
    greeting            TEXT,
    batch_number         INTEGER,
    status              TEXT NOT NULL,
    error_message         TEXT,
    draft_message_id      TEXT,
    sent_message_id       TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS near_duplicate_warnings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company_a     TEXT NOT NULL,
    company_b     TEXT NOT NULL,
    similarity    REAL NOT NULL,
    reviewed      INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create the database and tables if they don't already exist."""
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def now():
    return datetime.utcnow().isoformat()


def upsert_company(company_key, company_name, all_emails_json, poc_map_json):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT company_key FROM companies WHERE company_key = ?", (company_key,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE companies
                   SET company_name=?, all_emails=?, poc_map=?, updated_at=?
                   WHERE company_key=?""",
                (company_name, all_emails_json, poc_map_json, now(), company_key),
            )
        else:
            conn.execute(
                """INSERT INTO companies
                   (company_key, company_name, all_emails, poc_map,
                    last_contacted_email, rotation_index, times_contacted,
                    last_campaign_date, created_at, updated_at)
                   VALUES (?, ?, ?, ?, NULL, 0, 0, NULL, ?, ?)""",
                (company_key, company_name, all_emails_json, poc_map_json, now(), now()),
            )


def get_company(company_key):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM companies WHERE company_key = ?", (company_key,)
        ).fetchone()
        return dict(row) if row else None


def already_contacted_company_keys(batch_number=None):
    """Company keys that already have a SENT or DRAFT_CREATED log entry
    (i.e. should NOT be re-picked for a new batch)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT company_key FROM campaign_log
               WHERE status IN ('SENT', 'DRAFT_CREATED', 'DRAFT')"""
        ).fetchall()
        return {r["company_key"] for r in rows}


def next_batch_number():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(batch_number) as m FROM campaign_log"
        ).fetchone()
        return (row["m"] or 0) + 1


def record_log_entry(company_key, company_name, recipient_email, poc_first_name,
                      greeting, batch_number, status, error_message=None,
                      draft_message_id=None, sent_message_id=None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO campaign_log
               (company_key, company_name, recipient_email, poc_first_name,
                greeting, batch_number, status, error_message,
                draft_message_id, sent_message_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (company_key, company_name, recipient_email, poc_first_name,
             greeting, batch_number, status, error_message,
             draft_message_id, sent_message_id, now(), now()),
        )
        return conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]


def update_log_status(log_id, status, error_message=None,
                       draft_message_id=None, sent_message_id=None):
    with get_conn() as conn:
        conn.execute(
            """UPDATE campaign_log
               SET status=?, error_message=COALESCE(?, error_message),
                   draft_message_id=COALESCE(?, draft_message_id),
                   sent_message_id=COALESCE(?, sent_message_id),
                   updated_at=?
               WHERE id=?""",
            (status, error_message, draft_message_id, sent_message_id, now(), log_id),
        )


def update_rotation(company_key, contacted_email):
    with get_conn() as conn:
        conn.execute(
            """UPDATE companies
               SET last_contacted_email=?, rotation_index=rotation_index+1,
                   times_contacted=times_contacted+1, last_campaign_date=?,
                   updated_at=?
               WHERE company_key=?""",
            (contacted_email, now(), now(), company_key),
        )


def record_near_duplicate(company_a, company_b, similarity):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO near_duplicate_warnings
               (company_a, company_b, similarity, reviewed, created_at)
               VALUES (?, ?, ?, 0, ?)""",
            (company_a, company_b, similarity, now()),
        )


def get_failed_schedules():
    """Drafts that were created but never successfully sent —
    the 'VIEW FAILED SCHEDULES' equivalent."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM campaign_log
               WHERE status = 'DRAFT'
               ORDER BY created_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def export_report_rows():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT company_name, poc_first_name, recipient_email, batch_number,
                      status, error_message, draft_message_id, sent_message_id,
                      created_at
               FROM campaign_log ORDER BY created_at"""
        ).fetchall()
        return [dict(r) for r in rows]
