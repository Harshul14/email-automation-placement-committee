"""
user_profile.py
================
Manages per-user identity for the email campaign.

On first run (or when the user requests a fresh profile), prompts for:
  - Full name  (must match the 'Owner' column in the Excel DB exactly)
  - NMIMS sender email
  - Phone number
  - LinkedIn profile URL and display name
  - Mentor's NMIMS email address
  - Sector head's NMIMS email address (default: AARYESH.MISHRA450@nmims.in)

The profile is saved to a JSON file inside the campaign data directory
(Google Drive in Colab, local data/ otherwise), so it persists across
Colab sessions.  On subsequent runs the saved profile is shown and the
user is asked "Use this profile? [Y/N]" — one keypress instead of
re-entering every field.

WHAT IS NOT STORED HERE:
  - The NMIMS account password (asked via getpass() at send-time only).
  - Any email content or recipient data.
"""

import json
import os
from dataclasses import asdict, dataclass

import config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROFILE_FILENAME = "user_profile.json"
DEFAULT_SECTOR_HEAD = "AARYESH.MISHRA450@nmims.in"

_SEP = "=" * 60


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class UserProfile:
    """All identity fields that vary per committee member."""
    full_name: str          # e.g. "Poorvi Verma"  — must match Excel Owner col
    sender_email: str       # e.g. "POORVI.VERMA604@nmims.in"
    phone: str              # e.g. "+91-9850298018"
    linkedin_url: str       # e.g. "https://www.linkedin.com/in/poorvi-verma-80a784220/"
    linkedin_display: str   # e.g. "Poorvi Verma"  — as shown on LinkedIn
    mentor_email: str       # e.g. "SHAILVEE.GANDOTRA749@nmims.in"
    sector_head_email: str  # e.g. "AARYESH.MISHRA450@nmims.in"


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------
def _profile_path() -> str:
    """Absolute path of the saved profile JSON file."""
    return os.path.join(config.data_dir(), PROFILE_FILENAME)


def _load_saved():
    """Load and return a UserProfile from disk, or None if not found / corrupt."""
    path = _profile_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Validate all expected keys are present (guards against stale files
        # that are missing new fields added in later versions).
        expected = set(UserProfile.__dataclass_fields__)
        if not expected.issubset(data.keys()):
            missing = expected - data.keys()
            print(f"  ⚠  Saved profile is missing fields {missing} — re-prompting.")
            return None
        return UserProfile(**{k: data[k] for k in expected})
    except Exception as exc:
        print(f"  ⚠  Could not read saved profile ({exc}) — re-prompting.")
        return None


def _save(profile: UserProfile) -> None:
    """Write the profile to disk as JSON."""
    path = _profile_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(asdict(profile), fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def _validate_nmims_email(value: str):
    """Return an error message string, or None if the value is valid."""
    if not value.lower().endswith("@nmims.in"):
        return (
            "Must be an NMIMS email ending in @nmims.in "
            "(e.g. FIRSTNAME.LASTNAME123@nmims.in)"
        )
    if "@" not in value or value.startswith("@"):
        return "Must be a full email address including the local part before @"
    return None


def _validate_linkedin_url(value: str):
    """Return an error message string, or None if the value is valid."""
    cleaned = value.lower().rstrip("/")
    valid_prefixes = (
        "https://linkedin.com/in/",
        "https://www.linkedin.com/in/",
    )
    if not any(cleaned.startswith(p) for p in valid_prefixes):
        return (
            "Must be a full LinkedIn profile URL starting with "
            "https://www.linkedin.com/in/ "
            "(e.g. https://www.linkedin.com/in/yourname/)"
        )
    # Ensure there is a non-empty slug after the /in/ prefix
    for prefix in valid_prefixes:
        if cleaned.startswith(prefix):
            slug = cleaned[len(prefix):]
            if not slug:
                return "URL appears incomplete — include your LinkedIn slug after /in/"
    return None


def _validate_phone(value: str):
    """Basic phone sanity check — must contain at least 7 digits."""
    digits = [c for c in value if c.isdigit()]
    if len(digits) < 7:
        return (
            "Please enter a valid phone number with at least 7 digits "
            "(e.g. +91-9876543210)"
        )
    return None


# ---------------------------------------------------------------------------
# Interactive prompt helpers
# ---------------------------------------------------------------------------
def _ask(prompt: str, validator=None, default: str = None) -> str:
    """Prompt the user with optional validation and an optional default value.

    Loops until a valid, non-empty value is entered.
    """
    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"  {prompt}{suffix}: ").strip()
        if not raw and default:
            raw = default
        if not raw:
            print("    ⚠  This field cannot be empty. Please try again.")
            continue
        if validator:
            error = validator(raw)
            if error:
                print(f"    ⚠  {error}")
                continue
        return raw


def _display(profile: UserProfile) -> None:
    """Print a human-readable summary of a UserProfile."""
    print(f"    Name             : {profile.full_name}")
    print(f"    Sender email     : {profile.sender_email}")
    print(f"    Phone            : {profile.phone}")
    print(f"    LinkedIn URL     : {profile.linkedin_url}")
    print(f"    LinkedIn name    : {profile.linkedin_display}")
    print(f"    Mentor email     : {profile.mentor_email}")
    print(f"    Sector head email: {profile.sector_head_email}")


# ---------------------------------------------------------------------------
# Core workflow
# ---------------------------------------------------------------------------
def _prompt_fresh() -> UserProfile:
    """Interactively collect all identity fields from the user and save them."""
    print(f"\n{_SEP}")
    print("USER PROFILE SETUP")
    print(_SEP)
    print("Your details will be used in the email signature and the CC list.")
    print("They are saved locally so you won't be asked again next session.")
    print("Your password is NEVER stored here or anywhere on disk.\n")

    print("── Step 1 of 7: Your Name ──────────────────────────────────────")
    print("  ⚠  This MUST match your name in the 'Owner' column of the Excel")
    print("     DB exactly (same capitalisation, same spacing) so the filter")
    print("     only processes your own rows.")
    full_name = _ask("Your full name (as in Excel Owner column)")

    print("\n── Step 2 of 7: Your NMIMS Email ───────────────────────────────")
    sender_email = _ask(
        "Your NMIMS email (e.g. FIRSTNAME.LASTNAME123@nmims.in)",
        validator=_validate_nmims_email,
    )

    print("\n── Step 3 of 7: Phone Number ───────────────────────────────────")
    phone = _ask(
        "Your phone number (e.g. +91-9876543210)",
        validator=_validate_phone,
    )

    print("\n── Step 4 of 7: LinkedIn URL ───────────────────────────────────")
    linkedin_url = _ask(
        "Your LinkedIn profile URL (https://www.linkedin.com/in/...)",
        validator=_validate_linkedin_url,
    )

    print("\n── Step 5 of 7: LinkedIn Display Name ──────────────────────────")
    linkedin_display = _ask(
        "Your name as shown on LinkedIn (e.g. Poorvi Verma)",
    )

    print("\n── Step 6 of 7: Mentor Email ───────────────────────────────────")
    print("  This replaces the hardcoded mentor address in the CC list.")
    print("  (Previously: SHAILVEE.GANDOTRA749@nmims.in or")
    print("               AYUSHI.SRIVASTAVA073@nmims.in)")
    mentor_email = _ask(
        "Mentor's NMIMS email (e.g. FIRSTNAME.LASTNAME123@nmims.in)",
        validator=_validate_nmims_email,
    )

    print("\n── Step 7 of 7: Sector Head Email ──────────────────────────────")
    sector_head_email = _ask(
        "Sector head's NMIMS email",
        validator=_validate_nmims_email,
        default=DEFAULT_SECTOR_HEAD,
    )

    profile = UserProfile(
        full_name=full_name,
        sender_email=sender_email,
        phone=phone,
        linkedin_url=linkedin_url,
        linkedin_display=linkedin_display,
        mentor_email=mentor_email,
        sector_head_email=sector_head_email,
    )

    _save(profile)
    print(f"\n  ✔ Profile saved to: {_profile_path()}")
    print(_SEP)
    return profile


def load_or_prompt() -> UserProfile:
    """Load the saved profile or prompt for a fresh one.

    Algorithm:
      1. Try to load from ``user_profile.json`` in the campaign data dir.
      2. If found → display it and ask "Use this profile? [Y/N]".
         - Y → return the saved profile immediately.
         - N → fall through and prompt fresh.
      3. If not found (first run, or data dir was wiped) → prompt fresh.
      4. Save the fresh profile before returning.

    Returns:
        UserProfile: The active profile for this campaign run.
    """
    saved = _load_saved()

    if saved:
        print(f"\n{_SEP}")
        print("USER PROFILE  (loaded from saved data)")
        print(_SEP)
        _display(saved)
        answer = input("\n  Use this profile for this run? [Y/N]: ").strip().lower()
        if answer == "y":
            print("  ✔ Using saved profile.\n")
            return saved
        print("  Entering new profile details…\n")

    return _prompt_fresh()
