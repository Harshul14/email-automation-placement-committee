# PROMPT_DESIGN.md

## Runtime User Identity Prompt — Design Document

This document describes every design decision, edge case, and guardrail for
the interactive prompting system in `user_profile.py`.

---

## 1. Why Runtime Prompting Instead of Hardcoding?

The campaign is shared via a Git repository. Hardcoding one person's name,
email, phone number, and LinkedIn URL meant every new committee member had
to manually edit `config.py` before running — and risked committing someone
else's personal details to the repo history.

The runtime prompt approach means:
- **No code editing** required to switch users.
- **No personal data** is ever committed to Git.
- **Persistence via JSON** means the prompt only appears once per machine /
  Colab Drive — subsequent runs just show a one-line "Use saved profile? [Y/N]"
  confirmation.

---

## 2. What Is Prompted

| # | Field | Prompt Text | Validation | Default |
|---|-------|-------------|------------|---------|
| 1 | Full name | "Your full name (as in Excel Owner column)" | Non-empty | — |
| 2 | Sender NMIMS email | "Your NMIMS email (e.g. FIRSTNAME.LASTNAME123@nmims.in)" | Must end with `@nmims.in`; must have a non-empty local part | — |
| 3 | Phone | "Your phone number (e.g. +91-9876543210)" | Must contain ≥ 7 digits | — |
| 4 | LinkedIn URL | "Your LinkedIn profile URL (https://www.linkedin.com/in/...)" | Must start with `https://linkedin.com/in/` or `https://www.linkedin.com/in/`; slug after `/in/` must be non-empty | — |
| 5 | LinkedIn display name | "Your name as shown on LinkedIn (e.g. Poorvi Verma)" | Non-empty | — |
| 6 | Mentor NMIMS email | "Mentor's NMIMS email (e.g. FIRSTNAME.LASTNAME123@nmims.in)" | Must end with `@nmims.in` | — |
| 7 | Sector head NMIMS email | "Sector head's NMIMS email" | Must end with `@nmims.in` | `AARYESH.MISHRA450@nmims.in` |

---

## 3. Persistence

### Storage location
| Environment | Path |
|-------------|------|
| Google Colab (Drive mounted) | `/content/drive/MyDrive/nmims_email_campaign/data/user_profile.json` |
| Local / Colab without Drive | `<project_root>/data/user_profile.json` |

### Format
Plain JSON (UTF-8, pretty-printed with 2-space indent). Example:

```json
{
  "full_name": "Poorvi Verma",
  "sender_email": "POORVI.VERMA604@nmims.in",
  "phone": "+91-9850298018",
  "linkedin_url": "https://www.linkedin.com/in/poorvi-verma-80a784220/",
  "linkedin_display": "Poorvi Verma",
  "mentor_email": "SHAILVEE.GANDOTRA749@nmims.in",
  "sector_head_email": "AARYESH.MISHRA450@nmims.in"
}
```

> **WHAT IS NOT STORED:** The NMIMS Microsoft 365 account password is
> NEVER written to disk, JSON, the SQLite database, or any log file.
> It is requested via `getpass.getpass()` at send-time only and exists
> solely in process memory for the duration of that run.

### Stale-file protection
When `_load_saved()` reads the JSON, it checks that every field in the
current `UserProfile` dataclass is present. If a new field was added in a
newer version of the code, the stale file is detected, a warning is printed,
and the user is re-prompted to fill in all fields fresh. This prevents
silent use of an incomplete profile.

---

## 4. UX Flow — Every Path

```
Run starts
│
├── user_profile.json exists?
│     │
│     ├── YES → Display saved values
│     │          ↓
│     │         "Use this profile? [Y/N]"
│     │          ├── Y → Apply profile → continue campaign
│     │          └── N → Fall through to fresh prompt → save → continue
│     │
│     └── NO  → Fresh prompt (7 steps) → save → continue
│
└── (Profile validation / stale-file error)
      → Print ⚠ warning → Fall through to fresh prompt
```

---

## 5. Validation Edge Cases

### Full name (Step 1)
- **Edge case**: Name does not match the Excel `Owner` column.  
  **Impact**: `OWNER_FILTER` will not match any rows, producing an empty
  company list (`"No eligible companies remaining"`).  
  **Mitigation**: The prompt explicitly warns: *"This MUST match your name
  in the 'Owner' column of the Excel DB exactly (same capitalisation, same
  spacing)."*  
  **No auto-fix**: We deliberately do not auto-correct capitalisation. The
  Excel sheet is the source of truth; the user must enter their name exactly
  as it appears there.

### NMIMS email (Steps 2, 6, 7)
- **Edge case**: User enters a Gmail or personal address.  
  **Mitigation**: `@nmims.in` suffix validation loops until corrected.
- **Edge case**: User enters only `@nmims.in` with no local part.  
  **Mitigation**: The `startswith("@")` check catches this.
- **Edge case**: Mixed case (e.g. `poorvi.verma604@NMIMS.in`).  
  **Mitigation**: Comparison is `.lower()` so `@NMIMS.IN` is accepted.
  The stored value retains the user's casing (NMIMS SMTP auth is
  case-insensitive for the login, but we store as-entered to avoid
  surprising the user).

### Phone (Step 3)
- **Edge case**: User enters a phone with country code, spaces, dashes, or
  parentheses (e.g. `+91 (985) 029-8018`).  
  **Mitigation**: Validation strips all non-digit characters before counting;
  it accepts any format that yields ≥ 7 digits. The stored value is whatever
  the user typed — it appears verbatim in the signature.
- **Edge case**: User enters an extension number like `ext. 102`.  
  **Impact**: Passes validation (contains ≥ 7 digits if the main number is
  included). Appears verbatim in signature.

### LinkedIn URL (Step 4)
- **Edge case**: User copies the URL from the browser with trailing `/`.  
  **Mitigation**: The slug check strips trailing `/` before validating.
- **Edge case**: User enters `http://` instead of `https://`.  
  **Mitigation**: Only `https://` is accepted; user is re-prompted.
- **Edge case**: User enters `https://www.linkedin.com/in/` with nothing after.  
  **Mitigation**: Empty slug is detected and re-prompted.
- **Edge case**: User enters a LinkedIn company URL or post URL, not a profile.  
  **Mitigation**: We only accept `/in/` paths (personal profiles). Company
  URLs (`/company/`) will fail validation and be re-prompted.

### Mentor / Sector head email (Steps 6, 7)
- **Edge case**: The same person is both mentor and sector head.  
  **Impact**: That address appears twice in `PRODUCTION_CC_EMAILS`. This is
  benign — the recipient just gets one email with their address in CC twice,
  which most servers deduplicate silently.
- **Edge case**: User presses Enter on Step 7 without typing anything.  
  **Behaviour**: The default `AARYESH.MISHRA450@nmims.in` is used. This is
  the current sector head. If the sector head changes, the user must enter
  their new email explicitly.

---

## 6. What Happens When `apply_user_profile()` Is Called

`config.apply_user_profile(profile)` sets the following module-level
globals at runtime:

| Config variable | Source |
|----------------|--------|
| `config.SENDER_EMAIL` | `profile.sender_email` |
| `config.PRODUCTION_CC_EMAILS` | Fixed 3 + `mentor_email` + `sector_head_email` + Placement.Blr |
| `config.OWNER_FILTER` | `profile.full_name` |
| `config.SIGNATURE_HTML` | Built from `full_name`, `phone`, `linkedin_url`, `linkedin_display` |
| `config.SIGNATURE_PLAIN` | Same fields, plain text version |

> **Why not read from profile inside template_engine?**  
> All other modules already read from `config.*`. Introducing a direct
> dependency on `user_profile` in `template_engine` would create a
> tighter coupling than necessary. The single `apply_user_profile()` call
> in `campaign_runner.run()` keeps all profile-reading logic in one place.

---

## 7. MS Outlook Account Blocking — Full Risk Analysis

### Risk 1 — Wrong password looped many times (**HIGH**)
Microsoft 365 triggers account lockout after a configurable number of
failed authentication attempts (default: ~10). A committee member who
repeatedly mis-types their password can lock their NMIMS account.

**Mitigations in this codebase:**
- `getpass()` hides the password to reduce typos.
- A clear ⚠ WARNING is printed before `getpass()`:
  *"Entering the wrong password multiple times will lock your NMIMS account."*
- SMTP login is attempted once per run (not in a retry loop).

**What you must NOT do:**
- Do not modify the code to retry SMTP login on auth failure.

---

### Risk 2 — High send rate triggering spam filter (**MEDIUM**)
Microsoft 365 has per-mailbox throttling (commonly ~30 msg/min for
unlicensed/student accounts). Sending too fast raises the spam score.

**Mitigations in this codebase:**
- `SEND_DELAY_MIN = 4s`, `SEND_DELAY_MAX = 9s` inter-send random delay.
- `DAILY_COMPANY_LIMIT = 30` — maximum 30 emails per run.
- Single SMTP session reused across the batch (no repeated login/logout
  which itself looks suspicious).

---

### Risk 3 — High bounce / NDR rate (**MEDIUM**)
If many recipient emails are invalid (copied wrong into the Excel DB),
Microsoft's outbound spam filter will flag the account for a high
non-delivery report rate. After several sessions, outbound sending can
be temporarily restricted.

**Current mitigation:**
- `validators.py` strips obviously invalid email addresses at parse time.

**Remaining gap:**
- Valid-format but non-existent addresses (e.g. a person who left the
  company) still bounce at the SMTP server level. Monitor the Sent
  Items bounce rate; if > 10% of a batch bounces, pause and clean the DB.

---

### Risk 4 — Multiple runs on the same day (**LOW-MEDIUM**)
Running the campaign twice in one day effectively doubles the send rate.
Microsoft's daily send limit for student/standard M365 accounts is
typically 2,000 recipients/day (counting CC as additional recipients).
With 6 CC addresses per email × 30 companies = 210 recipients per run,
two runs/day = 420 recipients — still within limits, but approaching
territory where the pattern looks suspicious to ATP.

**Rule of thumb:** **one run per calendar day per sender account.**

---

### Risk 5 — Sending from Google Colab IP (**LOW**)
Colab VMs use Google datacenter IPs. Microsoft 365 authenticates by
username + password over STARTTLS, not by source IP, so this is
generally fine. However, if NMIMS IT has configured Conditional Access
policies restricting sign-in to certain IP ranges or regions, SMTP auth
from Colab will fail with an authentication error (not a lockout).

**If this happens:** Contact NMIMS IT to whitelist SMTP auth from
external IPs, or run the notebook locally.

---

### Risk 6 — Committed credentials (**CRITICAL — already prevented**)
The `.gitignore` must exclude:
- `data/user_profile.json` (contains personal email/phone/LinkedIn)
- `data/*.db` (campaign history)
- `data/drafts/` (saved .eml files)
- `logs/` (may contain email addresses)
- Any file containing a password

Check `.gitignore` includes these patterns before pushing.

---

## 8. Things That Will NEVER Cause a Block

- **The signature HTML itself** — HTML signatures are standard.
- **The CC list** — 5–6 internal recipients per email is normal.
- **The email subject** — "Invitation for Campus Hiring | NMIMS, Bengaluru"
  does not trigger spam filters.
- **The SharePoint links in the body** — Microsoft's own CDN; not flagged.
- **Re-running with a different user profile** — the SMTP auth username
  changes, but each account is independent.
