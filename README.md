# NMIMS Placement Committee — Email Campaign Tool

Draft-first, rotation-aware outreach tool for the Campus Connect email
campaign, built for Google Colab.

## Why not real Microsoft-scheduled sending?

True "schedule for a future date" delivery requires the Microsoft Graph
API, which requires an Azure AD (Entra ID) app registration in the
NMIMS tenant. You confirmed you can't do that (no self-service, no
admin route). Without Graph, there is no Microsoft-supported way to
tell Exchange "deliver this at 10:30 AM on the 19th" — SMTP has no such
concept, and IMAP can only file a draft, not schedule it.

So this tool does the next safest thing, agreed with you as the
fallback:

1. **Draft-first, always.** Every email is created as a real Outlook
   Draft via IMAP `APPEND`, and that draft's existence is verified
   before anything else happens.
2. **You decide when to run it.** "Scheduling" = you open Colab once a
   day and run the tool. It picks up to 30 companies that haven't been
   contacted yet, shows you a full preview, and only sends — via SMTP,
   in that same run — after you type `Y` at *two* separate
   confirmation prompts (once before creating drafts, once before
   sending them).
3. **No email is ever sent without a verified draft + your explicit
   confirmation.** If draft creation fails, if you say `N`, or if the
   send itself fails, the item stays as `DRAFT` in the database and in
   your real Outlook Drafts folder — never auto-sent, never silently
   dropped.

If your Azure AD situation changes later (self-service app registration
becomes available), the send/schedule step in `mail_client.py` and
`campaign_runner.py` is the only part that would need to change to add
true Graph-based deferred delivery — everything else (rotation,
dedup, DB, template rendering, fuzzy POC matching) stays as-is.

## What you actually provide vs. what was assumed

The original request assumed a Word template with an existing
"Aakriti" signature to replace, and an Independence Day banner image.
**Neither exists in the DOCX you provided** — it's a different,
image-free "Campus Connect" template with no signature block. Your
signature (from `config.py`) is therefore *added*, not *replaced*.

## Setup (Google Colab)

```python
from google.colab import drive
drive.mount('/content/drive')

!pip install rapidfuzz python-docx --quiet
# pandas / openpyxl are already present in Colab
```

Upload (or `git clone`) this `email_campaign/` folder into your Colab
session, with:

- `DB_Week_of_14_08_2026_Harshul_Varshney.xlsx` (or update
  `config.EXCEL_FILE`) in the project root
- `templates/email_template.docx` (the Campus Connect template)

Then:

```python
%cd email_campaign
import main
main.run_campaign()
```

The database (`data/campaign_state_test.db` or `campaign_state.db`)
and logs are written to
`/content/drive/MyDrive/nmims_email_campaign/` so they survive Colab
session restarts. **This matters** — without Drive, your rotation and
"already contacted" history would reset every session and you could
re-email the same companies.

## Modes

Edit the single line in `config.py`:

```python
MODE = "TEST"        # or "PRODUCTION"
```

- **TEST**: every email is redirected to `harshul7713@gmail.com`,
  CC only `harshul.spacece@gmail.com`. The production CC list is
  disabled. Uses a separate database (`campaign_state_test.db`) so
  testing can never corrupt production history.
- **PRODUCTION**: sends to the real Excel recipient, CCs the fixed
  Placement Committee list, uses `campaign_state.db`.

**Recommended first run: TEST mode**, confirm draft creation only (say
`N` at the send-confirmation step), open your real Outlook Drafts
folder and inspect them. Only flip to `PRODUCTION` once you're happy.

## How recipient selection actually works

Your Excel's `Contact Person`, `Designation`, and `Email Id` columns
are all comma-separated — but their counts frequently don't match
(e.g. 2 names but 3 emails on the same row). A positional match would
silently attribute the wrong person to the wrong email, so instead:

- Each email's local-part is fuzzy-matched (RapidFuzz) against every
  candidate name on that row.
- A confident match (score ≥ `FUZZY_MATCH_THRESHOLD`, default 72) uses
  that person's **first name only** and their **Mr./Ms.** exactly as
  written in the Excel — never guessed.
- No confident match → `Dear Team,` for that specific email. Other
  emails on the same row can still resolve to real names independently.

On the real file (175 usable companies, 417 valid emails after
filtering), this resolves **326 emails to a named greeting** and
correctly falls back to **91 "Dear Team,"** greetings.

## Contact rotation & batching

- Company key = normalized company name (whitespace/case-insensitive,
  punctuation-insensitive). Companies with genuinely different names
  (e.g. "ABC Ltd." vs "ABC Limited") are **not** auto-merged — the
  parser logs a `near_duplicate_warnings` DB entry for manual review
  instead, per the brief's "don't silently merge" rule. On the actual
  file, zero exact or near-duplicates were found.
- Each batch picks up to 30 **unique companies** not yet `SENT` or
  `DRAFT`/`DRAFT_CREATED`. A company with 3 emails still counts as one
  company per batch.
- Within a company, contacts rotate round-robin based on
  `last_contacted_email` stored in SQLite — campaign 1 uses contact A,
  campaign 2 uses contact B, etc., restarting once all are cycled.
- Restarting the script mid-batch does **not** resend anything already
  logged as `SENT`/`DRAFT_CREATED`/`DRAFT` — it picks up from the next
  eligible company.

## Status model

```
GENERATED      content built & validated
DRAFT_CREATED  verified in Outlook Drafts via IMAP
SENT           SMTP send succeeded, after your explicit confirmation
DRAFT          draft exists but was NOT sent (you said N, or send failed)
FAILED         draft creation itself failed; nothing reached Outlook
```

Run `python main.py --failed` any time to list everything stuck at
`DRAFT` (created but not sent) for manual review/recovery.
Run `python main.py --export` to dump the full campaign log to
`campaign_report.xlsx`.

## Security

- Password is requested via `getpass()` at the start of each run.
  Never written to disk, never logged, never stored in SQLite.
- No IP rotation, header spoofing, or throttling evasion of any kind —
  if Microsoft returns a throttling/security error, the run should be
  stopped and retried later, not automatically retried in a loop.

## Testing

`test_campaign.py` covers the logic that doesn't require a live
mailbox: multi-value email parsing, fuzzy POC matching (including the
mismatched-count case from your real data), rotation, batch-size
limits, within-batch duplicate protection, and TEST/PRODUCTION mode
isolation. Run:

```bash
pip install -r requirements.txt pytest
pytest test_campaign.py -v
```

Draft creation and send (`mail_client.py`) can only be verified against
a live mailbox — do that via a real TEST-mode run, inspecting your
actual Outlook Drafts folder, before ever switching to PRODUCTION.

## Known limitations

- No true future-dated scheduling (see above) — this is the single
  biggest deviation from the original brief, and it's structural
  (no Azure AD access), not a shortcut.
- Fuzzy POC matching is heuristic. Spot-check the `Dear Team,` count
  after your first TEST run — if it looks too high, lowering
  `FUZZY_MATCH_THRESHOLD` slightly may recover more names, at the cost
  of more risk of a wrong match.
- Near-duplicate company names are flagged, never auto-merged — check
  the `near_duplicate_warnings` table occasionally as your Excel grows.
