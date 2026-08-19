"""
campaign_runner.py
====================
Orchestrates one campaign run end-to-end:

  1. Load & validate Excel -> company records  [FILE UPLOADED AT RUNTIME]
  2. Select today's batch (count chosen at runtime by user)
  3. Validate every piece of content, build personalized HTML
  4. PREVIEW -> user confirms [Y/N]
  5. Create Outlook Drafts via IMAP, verify each -> DRAFT_CREATED
     NOTE: rotation is advanced at this point (draft created), not at send.
  6. PREVIEW of successfully created drafts -> user confirms [Y/N]
  7. On Y: SMTP send now, mark SENT. On N or any failure: leave as DRAFT,
     never auto-send.

Rotation policy (per spec sections 13-14, 43, 45):
  - last_contacted_email and rotation_index are updated in the DB as soon
    as a draft is successfully created for a company.  This ensures that
    even when the user declines sending (or the send fails), the NEXT run
    for that company picks the NEXT contact in the round-robin sequence
    rather than repeating the same address.

Runtime / Colab persistence:
  - The SQLite DB must live on Google Drive (DRIVE_DATA_DIR in config.py).
    If the runtime resets and the DB is missing, a startup warning is shown
    so the operator can abort before accidentally re-sending to companies
    that were already drafted/sent in a previous session.

There is deliberately no code path that sends an email without both a
successfully-verified draft AND an explicit user confirmation.
"""

import getpass
import io
import json
import os
import sys

import config
import database
from contact_matcher import greeting_for, select_next_contact
from excel_parser import load_companies
from mail_client import MailSession
from template_engine import render_html, render_plaintext_fallback
from logger_setup import get_logger


def _load_excel_runtime():
    """Load the recipient Excel file at runtime.
    Supports Google Colab upload, Jupyter ipywidgets, or plain input().
    Returns the resolved file path string to pass to load_companies()."""

    # --- Google Colab ---
    try:
        from google.colab import files
        print("Running in Google Colab. Please upload your Excel DB file:")
        uploaded = files.upload()
        if not uploaded:
            print("No file uploaded. Exiting.")
            sys.exit(1)
        excel_path = list(uploaded.keys())[0]
        print(f"Uploaded: {excel_path}")
        return excel_path
    except ImportError:
        pass  # Not in Colab

    # --- Jupyter Notebook (ipywidgets) ---
    try:
        import ipywidgets as widgets
        from IPython.display import display
        import time as _time

        print("Running in Jupyter. Use the upload button to select your Excel DB file:")
        uploader = widgets.FileUpload(accept=".xlsx,.xls", multiple=False)
        display(uploader)

        timeout, elapsed = 60, 0
        while not uploader.value and elapsed < timeout:
            _time.sleep(1)
            elapsed += 1

        if not uploader.value:
            print("No file uploaded within timeout. Exiting.")
            sys.exit(1)

        filename = list(uploader.value.keys())[0]
        content = list(uploader.value.values())[0]["content"]
        # Write to disk so load_companies() can open it normally
        with open(filename, "wb") as f:
            f.write(content)
        print(f"Loaded: {filename}")
        return filename
    except ImportError:
        pass  # No ipywidgets

    # --- Plain Python: ask for file path ---
    while True:
        excel_path = input("Enter the path to your Excel DB file: ").strip()
        if not excel_path:
            print("Path cannot be empty. Please try again.")
            continue
        if not os.path.exists(excel_path):
            print(f"File not found: '{excel_path}'. Please check the path and try again.")
            continue
        print(f"Loading: {excel_path}")
        return excel_path


def _prompt_email_count(total_companies):
    """Ask the user how many companies to email in this run.
    Returns an integer between 1 and total_companies (inclusive)."""
    print(f"\nTotal eligible companies found: {total_companies}")
    while True:
        user_input = input(
            f"Enter number of companies to email this run "
            f"(or press Enter to use daily limit of {config.DAILY_COMPANY_LIMIT}): "
        ).strip()

        if user_input == "":
            chosen = min(config.DAILY_COMPANY_LIMIT, total_companies)
            print(f"Using default daily limit: {chosen}")
            return chosen

        if not user_input.isdigit() or int(user_input) <= 0:
            print("Please enter a valid positive integer.")
            continue

        chosen = int(user_input)
        if chosen > total_companies:
            print(f"Cannot exceed total eligible companies ({total_companies}). Please enter a smaller number.")
            continue

        return chosen

logger = get_logger()


def sync_companies_to_db(records):
    """Upsert every parsed company into the DB (idempotent)."""
    for r in records:
        database.upsert_company(
            r.company_key,
            r.company_name,
            json.dumps(r.emails),
            json.dumps(r.poc_map),
        )


def select_batch(records, limit=None):
    """Pick up to `limit` companies that have not already been SENT or drafted,
    and choose the next rotation contact for each.
    If limit is None, falls back to config.DAILY_COMPANY_LIMIT."""
    if limit is None:
        limit = config.DAILY_COMPANY_LIMIT
    already = database.already_contacted_company_keys()
    seen_in_this_batch = set()
    batch = []
    for r in records:
        if r.company_key in already or r.company_key in seen_in_this_batch:
            continue
        company_row = database.get_company(r.company_key)
        next_email = select_next_contact(company_row, r.poc_map, r.emails)
        if not next_email:
            continue
        poc_entry = r.poc_map.get(next_email, {})
        greeting = greeting_for(poc_entry)
        batch.append({
            "company_key": r.company_key,
            "company_name": r.company_name,
            "email": next_email,
            "poc_first_name": poc_entry.get("first_name"),
            "greeting": greeting,
        })
        seen_in_this_batch.add(r.company_key)
        if len(batch) >= limit:
            break
    return batch


def print_preview(batch, stage_label):
    print("=" * 60)
    print(f"{stage_label}")
    print("=" * 60)
    for i, item in enumerate(batch, start=1):
        print(f"{i:02d}. {item['company_name']}")
        print(f"    To: {item['email']}")
        print(f"    Greeting: {item['greeting']}")
    print("=" * 60)
    if config.is_test_mode():
        print("TEST MODE — sending to real recipients with test CC list:")
        print("CC:", ", ".join(config.TEST_CC_EMAILS))
    print()


def confirm(prompt_text):
    answer = input(f"{prompt_text} [Y/N]: ").strip().lower()
    return answer == "y"


def run():
    # ------------------------------------------------------------------
    # Startup: warn if the campaign DB doesn't exist yet (e.g. Colab
    # runtime was reset and Google Drive wasn't mounted, which would wipe
    # all rotation/dedup history and risk re-sending to prior companies).
    # ------------------------------------------------------------------
    import os
    db_file = config.db_path()
    db_is_new = not os.path.exists(db_file)
    database.init_db()

    if db_is_new:
        print("\n" + "!" * 60)
        print("WARNING: No existing campaign database was found.")
        print(f"  Expected DB path: {db_file}")
        print("This could mean:")
        print("  • First-ever run — a fresh DB has just been created (OK).")
        print("  • Colab runtime was reset without Google Drive mounted,")
        print("    which DELETED all rotation history. Re-running now could")
        print("    send duplicate emails to companies already contacted.")
        print("! " * 30)
        if not confirm("Continue with a fresh/empty database?"):
            print("Aborted. Please mount Google Drive and retry.")
            return

    print(f"\nMODE = {config.MODE}")
    if config.is_test_mode():
        print("TEST MODE ACTIVE")
        print("ALL EMAILS WILL BE REDIRECTED TO:", config.TEST_REDIRECT_EMAIL)
        print("CC list (test): ", ", ".join(config.TEST_CC_EMAILS))

    # --- Runtime: upload/select Excel DB file ---
    excel_file = _load_excel_runtime()
    records, skipped = load_companies(excel_file, owner_filter=config.OWNER_FILTER)
    sync_companies_to_db(records)

    # --- Runtime: choose how many companies to email ---
    eligible_count = len(records)
    chosen_limit = _prompt_email_count(eligible_count)
    print(f"\nPreparing to send {chosen_limit} emails out of {eligible_count} total eligible companies.\n")

    batch = select_batch(records, limit=chosen_limit)
    if not batch:
        print("No eligible companies remaining for a new batch. Nothing to do.")
        return

    print_preview(batch, "NEXT BATCH PREVIEW")
    if not confirm("Confirm creation of drafts?"):
        print("Aborted before draft creation. No emails created or sent.")
        return

    print("\nEnter your NMIMS account password (used only for this run, never stored):")
    password = getpass.getpass()

    session = MailSession(password)
    session.connect()

    batch_number = database.next_batch_number()
    draft_results = []  # list of dicts: item, log_id, msg, status

    try:
        for item in batch:
            # TEST mode MUST redirect To: to the test address (spec §7-8).
            # PRODUCTION uses the real company email.
            if config.is_test_mode():
                to_email = config.TEST_REDIRECT_EMAIL
            else:
                to_email = item["email"]
            cc_list = config.active_cc_list()  # test CC in TEST, full CC in PRODUCTION

            html_body = render_html(item["greeting"], item["company_name"])
            plaintext_body = render_plaintext_fallback(item["greeting"], item["company_name"])

            log_id = database.record_log_entry(
                company_key=item["company_key"],
                company_name=item["company_name"],
                recipient_email=to_email,
                poc_first_name=item["poc_first_name"],
                greeting=item["greeting"],
                batch_number=batch_number,
                status="GENERATED",
            )

            msg = session.build_message(
                to_email, config.EMAIL_SUBJECT, html_body, plaintext_body, cc_list
            )

            try:
                draft_id = session.create_draft(msg, company_name=item["company_name"])
                # Advance rotation NOW (at draft-created time), not only at send.
                # This ensures that if the user declines sending, or the send
                # fails, the NEXT run for this company still picks the NEXT
                # contact in the round-robin — never repeating the same address.
                database.update_rotation(item["company_key"], item["email"])
                database.update_log_status(log_id, "DRAFT_CREATED", draft_message_id=draft_id)
                draft_results.append({"item": item, "log_id": log_id, "msg": msg,
                                       "to_email": to_email, "cc_list": cc_list, "ok": True})
                logger.info(f"Draft created for {item['company_name']} -> {to_email} "
                            f"(rotation advanced to next contact)")
            except Exception as e:
                database.update_log_status(log_id, "FAILED", error_message=str(e))
                draft_results.append({"item": item, "log_id": log_id, "ok": False, "error": str(e)})
                logger.error(f"Draft creation FAILED for {item['company_name']}: {e}")

        succeeded = [d for d in draft_results if d["ok"]]
        failed = [d for d in draft_results if not d["ok"]]

        print(f"\nTotal companies: {len(batch)}")
        print(f"Drafts created: {len(succeeded)}")
        print(f"Failed: {len(failed)}")
        for d in failed:
            print(f"  FAILED: {d['item']['company_name']} — {d['error']}")

        if not succeeded:
            print("No drafts were successfully created. Nothing to send.")
            return

        print_preview([d["item"] for d in succeeded], "DRAFTS CREATED — READY TO SEND")
        if not confirm("Confirm sending of successfully created drafts?"):
            print("Drafts left in Outlook, marked DRAFT. Nothing was sent.")
            for d in succeeded:
                database.update_log_status(d["log_id"], "DRAFT")
            return

        sent_count = 0
        for i, d in enumerate(succeeded):
            try:
                # Skip the inter-send delay for the very first email
                sent_id = session.send(d["msg"], d["to_email"], d["cc_list"],
                                       inter_send_delay=(i > 0))
                # NOTE: update_rotation() was already called at DRAFT_CREATED.
                # Do NOT call it again here — that would double-advance the index.
                database.update_log_status(d["log_id"], "SENT", sent_message_id=sent_id)
                sent_count += 1
                logger.info(f"Sent: {d['item']['company_name']} -> {d['to_email']}")
            except Exception as e:
                database.update_log_status(d["log_id"], "DRAFT", error_message=str(e))
                logger.error(f"Send FAILED for {d['item']['company_name']}: {e} — left as DRAFT")

        print(f"\nSent: {sent_count}")
        print(f"Still Draft (send failed): {len(succeeded) - sent_count}")

    finally:
        session.close()


def view_failed_schedules():
    for row in database.get_failed_schedules():
        print(f"{row['company_name']} | {row['recipient_email']} | "
              f"draft_id={row['draft_message_id']} | error={row['error_message']} | "
              f"{row['created_at']}")


def export_report(output_path="campaign_report.xlsx"):
    import pandas as pd
    rows = database.export_report_rows()
    df = pd.DataFrame(rows)
    df.to_excel(output_path, index=False)
    print(f"Report exported to {output_path}")
