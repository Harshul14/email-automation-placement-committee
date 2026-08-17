"""
config.py
=========
Single source of truth for campaign configuration.
Flip MODE between "TEST" and "PRODUCTION" here — nothing else in the
codebase needs to change.

IMPORTANT (read this before running):
- No password, token, or secret is ever stored in this file or anywhere
  on disk. The account password is asked for interactively (getpass) at
  the start of every run and is kept only in memory for that run.
- This project uses SMTP + IMAP with your NMIMS Microsoft 365 account,
  the same auth method your original Independence Day script used.
  There is NO Microsoft Graph / OAuth here, because that requires an
  Azure AD app registration, which you confirmed is not available to you.
  A direct consequence: there is no true "schedule for a future date"
  capability. See README.md ("Why not real scheduling?") for the full
  explanation. What this tool DOES give you is a mandatory Draft-first
  safety checkpoint (via IMAP) before anything is ever sent.
"""

import os

# ---------------------------------------------------------------------
# MODE: "TEST" or "PRODUCTION" — the only line you need to touch daily
# ---------------------------------------------------------------------
MODE = "TEST"  # change to "PRODUCTION" only after verifying TEST drafts

# ---------------------------------------------------------------------
# Google Drive persistence (Colab)
# ---------------------------------------------------------------------
# Colab's local disk is wiped every session. The SQLite database MUST
# live on Drive or your rotation/dedup history disappears daily and you
# risk re-contacting companies. main.py mounts Drive automatically.
DRIVE_DATA_DIR = "/content/drive/MyDrive/nmims_email_campaign/data"
DRIVE_LOG_DIR = "/content/drive/MyDrive/nmims_email_campaign/logs"

# Local fallback (only used if not running in Colab / Drive unavailable)
LOCAL_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LOCAL_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

# ---------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------
SENDER_EMAIL = "harshul.varshney447@nmims.in"
SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
# IMAP is disabled on this tenant — see mail_client.py for details.
# IMAP_HOST = "outlook.office365.com"
# IMAP_PORT = 993
# DRAFTS_FOLDER = "Drafts"  # Outlook's IMAP drafts folder name

# ---------------------------------------------------------------------
# Production CC list (NEVER used in TEST mode)
# ---------------------------------------------------------------------
PRODUCTION_CC_EMAILS = [
    "SHUBHAM.BANSAL654@nmims.in",
    "SHAKSHI.SHAH880@nmims.in",
    "BRYAN.PAES025@nmims.in",
    "AARYESH.MISHRA450@nmims.in",
    "AYUSHI.SRIVASTAVA073@nmims.in",
]

# ---------------------------------------------------------------------
# Test mode redirection (protects real recipients during development)
# ---------------------------------------------------------------------
TEST_TO_EMAIL = "harshul7713@gmail.com"
TEST_CC_EMAILS = ["harshul.spacece@gmail.com"]

# ---------------------------------------------------------------------
# Batch / campaign settings
# ---------------------------------------------------------------------
DAILY_COMPANY_LIMIT = 30           # unique companies per campaign day
FUZZY_MATCH_THRESHOLD = 72         # RapidFuzz score (0-100) to accept a POC<->email match
OWNER_FILTER = "Harshul Varshney"  # only process rows owned by this person

# ---------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------
EXCEL_FILE = "DB_Week_of_14_08_2026_Harshul_Varshney.xlsx"
EXCEL_SHEET = "DB"
DOCX_TEMPLATE = "templates/email_template.docx"

# ---------------------------------------------------------------------
# Signature (appended fresh — the source template has no signature block)
# ---------------------------------------------------------------------
SIGNATURE_HTML = """
<p style="margin-top:0; margin-bottom:0;">
Best Regards,<br>
<strong>Harshul Varshney</strong><br>
Member | Placement Committee<br>
<strong>SVKM's Narsee Monjee Institute of Management Studies,</strong><br>
Bannerghatta Main Road,<br>
Bengaluru - 560083<br>
Cell: +91-9310188008<br>
LinkedIn: <a href="https://www.linkedin.com/in/harshul-varshney" style="color:#000099; text-decoration:underline;">Harshul Varshney</a>
</p>
"""

EMAIL_SUBJECT = "Campus Connect Program – NMIMS Bengaluru"

# Real destination URLs extracted from the Safelinks-wrapped hyperlinks
# in the source DOCX (the safelinks are Outlook's own rewriting of these).
LINKEDIN_URL = "https://www.linkedin.com/company/corporate-relations-nmims-bengaluru/"
WEBSITE_URL = "https://bengaluru.nmims.edu/"


def data_dir():
    """Return the active data directory, creating it if needed."""
    path = DRIVE_DATA_DIR if os.path.isdir("/content/drive") else LOCAL_DATA_DIR
    os.makedirs(path, exist_ok=True)
    return path


def log_dir():
    path = DRIVE_LOG_DIR if os.path.isdir("/content/drive") else LOCAL_LOG_DIR
    os.makedirs(path, exist_ok=True)
    return path


def db_path():
    fname = "campaign_state_test.db" if MODE == "TEST" else "campaign_state.db"
    return os.path.join(data_dir(), fname)


def active_cc_list():
    return TEST_CC_EMAILS if MODE == "TEST" else PRODUCTION_CC_EMAILS


def is_test_mode():
    return MODE.upper() == "TEST"
