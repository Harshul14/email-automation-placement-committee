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
MODE = "PRODUCTION"  # change to "PRODUCTION" only after verifying TEST drafts
# MODE = "TEST"  # change to "PRODUCTION" only after verifying TEST drafts

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
# SENDER_EMAIL is set at runtime by apply_user_profile() — do not hardcode.
SENDER_EMAIL = None  # type: str  # e.g. "FIRSTNAME.LASTNAME123@nmims.in"
SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
# IMAP is disabled on this tenant — see mail_client.py for details.
# IMAP_HOST = "outlook.office365.com"
# IMAP_PORT = 993
# DRAFTS_FOLDER = "Drafts"  # Outlook's IMAP drafts folder name

# ---------------------------------------------------------------------
# Production CC list (NEVER used in TEST mode)
# ---------------------------------------------------------------------
# Fixed members who are always CC'd regardless of who runs the campaign.
_FIXED_CC = [
    "SHUBHAM.BANSAL654@nmims.in",
    "SHAKSHI.SHAH880@nmims.in",
    "BRYAN.PAES025@nmims.in",
    "Placement.Blr@nmims.edu",
]
# PRODUCTION_CC_EMAILS is rebuilt at runtime by apply_user_profile().
# mentor_email and sector_head_email slots are injected there.
PRODUCTION_CC_EMAILS = []  # type: list[str]

# ---------------------------------------------------------------------
# Test mode settings (spec sections 7-8)
# In TEST mode:
#   To:  is redirected to TEST_REDIRECT_EMAIL (real recipients NEVER used)
#   CC:  is replaced with TEST_CC_EMAILS
# The production CC addresses are NEVER included in TEST mode.
# ---------------------------------------------------------------------
TEST_REDIRECT_EMAIL = "harshul7713@gmail.com"   # spec §7: hard-redirect To:
TEST_CC_EMAILS = [
    # "poorvi.verma604@nmims.in",
    "harshul.spacece@gmail.com",
]

# ---------------------------------------------------------------------
# Batch / campaign settings
# ---------------------------------------------------------------------
DAILY_COMPANY_LIMIT = 30           # unique companies per campaign day
FUZZY_MATCH_THRESHOLD = 72         # RapidFuzz score (0-100) to accept a POC<->email match
# OWNER_FILTER is set at runtime by apply_user_profile() — do not hardcode.
OWNER_FILTER = None  # type: str  # must match 'Owner' column in Excel exactly

# ---------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------
EXCEL_FILE = "DB_Week_of_14_08_2026_Harshul_Varshney.xlsx"
EXCEL_SHEET = "DB"
DOCX_TEMPLATE = "templates/email_template.docx"

# ---------------------------------------------------------------------
# Signature (appended fresh — the source template has no signature block)
# ---------------------------------------------------------------------
# SIGNATURE_HTML and SIGNATURE_PLAIN are built at runtime by apply_user_profile().
# They are None until that function is called.
SIGNATURE_HTML = None   # type: str  # full HTML <p> block for email body
SIGNATURE_PLAIN = None  # type: str  # plain-text equivalent for fallback body

EMAIL_SUBJECT = "Invitation for Campus Hiring | NMIMS, Bengaluru"

# SharePoint document links embedded in the "Invitation for Campus Hiring" template.
# Fill in your own SharePoint URLs here before running the campaign.
CORPORATE_PRESENTATION_URL = "https://svkmmumbai-my.sharepoint.com/:b:/g/personal/ayushi_srivastava073_nmims_in/IQCQhOPTOBkBRKf75wOYM6jPAfpCDwGJAg6mHti7_Td8LuY?xsdata=MDV8MDJ8anVuaW9ycGxhY2VtZW50Y29tbWl0dGVlMjAyNi0yN0BzdmttbXVtYmFpLm9ubWljcm9zb2Z0LmNvbXxlNzJkNjAzNDUwNDI0YWI4OTc3OTA4ZGVmZmIxY2E0OXxkMWYxNDM0OGYxYjU0YTA5YWM5OTdlYmYyMTNjYmM4MXwwfDB8NjM5MjI5MzM2MjM2MzgwOTQ3fFVua25vd258VFdGcGJHWnNiM2Q4ZXlKRmJYQjBlVTFoY0draU9uUnlkV1VzSWxZaU9pSXdMakF1TURBd01DSXNJbEFpT2lKWGFXNHpNaUlzSWtGT0lqb2lUV0ZwYkNJc0lsZFVJam95ZlE9PXwwfHx8&sdata=NnNiYzJmZUpNVUZ5TkRWR0RsWlRCT2hud0FtNURSYzhSMjF2cnZGaTl0ND0%3d"  # TODO: paste your Corporate Presentation SharePoint link
PLACEMENT_BROCHURE_URL = "https://svkmmumbai-my.sharepoint.com/:b:/g/personal/ayushi_srivastava073_nmims_in/IQBkTwt4IOy_TaiFABDo5po5AfqpeqFI5JoX-b9LBG_-x5Y?e=fwFUt9&xsdata=MDV8MDJ8anVuaW9ycGxhY2VtZW50Y29tbWl0dGVlMjAyNi0yN0BzdmttbXVtYmFpLm9ubWljcm9zb2Z0LmNvbXxlNzJkNjAzNDUwNDI0YWI4OTc3OTA4ZGVmZmIxY2E0OXxkMWYxNDM0OGYxYjU0YTA5YWM5OTdlYmYyMTNjYmM4MXwwfDB8NjM5MjI5MzM2MjM2NDAyNDIwfFVua25vd258VFdGcGJHWnNiM2Q4ZXlKRmJYQjBlVTFoY0draU9uUnlkV1VzSWxZaU9pSXdMakF1TURBd01DSXNJbEFpT2lKWGFXNHpNaUlzSWtGT0lqb2lUV0ZwYkNJc0lsZFVJam95ZlE9PXwwfHx8&sdata=dFVJYlprZ3VmdVdYQ0MrY3k4cS90T01OMkdxeE9OZVgyVXBxZmV2UU1KMD0%3d"       # TODO: paste your Placement Brochure SharePoint link


def apply_user_profile(profile) -> None:
    """Inject a UserProfile into all config fields that were previously hardcoded.

    Must be called once at the start of every campaign run, before any
    config-dependent code (campaign_runner, template_engine, mail_client)
    reads SENDER_EMAIL, PRODUCTION_CC_EMAILS, OWNER_FILTER, or SIGNATURE_*.

    Args:
        profile: a user_profile.UserProfile dataclass instance.
    """
    global SENDER_EMAIL, PRODUCTION_CC_EMAILS, OWNER_FILTER
    global SIGNATURE_HTML, SIGNATURE_PLAIN

    SENDER_EMAIL = profile.sender_email

    # Build CC list: fixed committee members + runtime mentor + runtime sector head.
    # NOTE: sender_email is deliberately NOT added to CC — it is already in
    # the From: field and appears in Sent Items automatically.
    PRODUCTION_CC_EMAILS = [
        "SHUBHAM.BANSAL654@nmims.in",
        "SHAKSHI.SHAH880@nmims.in",
        "BRYAN.PAES025@nmims.in",
        profile.mentor_email,
        profile.sector_head_email,
        "Placement.Blr@nmims.edu",
    ]

    OWNER_FILTER = profile.full_name

    SIGNATURE_HTML = (
        f'\n<p style="margin-top:0; margin-bottom:0;">\n'
        f'Best Regards,<br>\n'
        f'<strong>{profile.full_name}</strong><br>\n'
        f'Member | Placement Committee<br>\n'
        f"<strong>SVKM's Narsee Monjee Institute of Management Studies,</strong><br>\n"
        f'Bannerghatta Main Road,<br>\n'
        f'Bengaluru - 560083<br>\n'
        f'Cell: {profile.phone}<br>\n'
        f'LinkedIn: <a href="{profile.linkedin_url}" '
        f'style="color:#000099; text-decoration:underline;">'
        f'{profile.linkedin_display}</a>\n'
        f'</p>\n'
    )

    SIGNATURE_PLAIN = (
        f"Best Regards,\n"
        f"{profile.full_name}\n"
        f"Member | Placement Committee\n"
        f"SVKM's Narsee Monjee Institute of Management Studies,\n"
        f"Bannerghatta Main Road, Bengaluru - 560083\n"
        f"Cell: {profile.phone}\n"
        f"LinkedIn: {profile.linkedin_url}\n"
    )


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
    """Return the correct CC list for the current mode.
    TEST  → limited test CC list (real recipients still receive the mail)
    PROD  → full production CC list
    """
    return TEST_CC_EMAILS if MODE == "TEST" else PRODUCTION_CC_EMAILS


def is_test_mode():
    return MODE.upper() == "TEST"
