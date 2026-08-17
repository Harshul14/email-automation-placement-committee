"""
campaign_runner.py
====================
Orchestrates one campaign run end-to-end:

  1. Load & validate Excel -> company records
  2. Select today's batch (<= DAILY_COMPANY_LIMIT companies not yet
     contacted), one contact per company via rotation
  3. Validate every piece of content, build personalized HTML
  4. PREVIEW -> user confirms [Y/N]
  5. Create Outlook Drafts via IMAP, verify each -> DRAFT_CREATED
  6. PREVIEW of successfully created drafts -> user confirms [Y/N]
  7. On Y: SMTP send now, mark SENT. On N or any failure: leave as DRAFT,
     never auto-send.

There is deliberately no code path that sends an email without both a
successfully-verified draft AND an explicit user confirmation.
"""

import getpass
import json

import config
import database
from contact_matcher import greeting_for, select_next_contact
from excel_parser import load_companies
from mail_client import MailSession
from template_engine import render_html, render_plaintext_fallback
from logger_setup import get_logger

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


def select_batch(records):
    """Pick up to DAILY_COMPANY_LIMIT companies that have not already
    been SENT or drafted, and choose the next rotation contact for each."""
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
        if len(batch) >= config.DAILY_COMPANY_LIMIT:
            break
    return batch


def print_preview(batch, stage_label):
    print("=" * 60)
    print(f"{stage_label}")
    print("=" * 60)
    for i, item in enumerate(batch, start=1):
        display_to = config.TEST_TO_EMAIL if config.is_test_mode() else item["email"]
        print(f"{i:02d}. {item['company_name']}")
        print(f"    To: {display_to}")
        print(f"    Greeting: {item['greeting']}")
    print("=" * 60)
    if config.is_test_mode():
        print("TEST MODE ACTIVE — ALL EMAILS WILL BE REDIRECTED TO:", config.TEST_TO_EMAIL)
        print("Production CC list is DISABLED in TEST mode.")
    print()


def confirm(prompt_text):
    answer = input(f"{prompt_text} [Y/N]: ").strip().lower()
    return answer == "y"


def run():
    database.init_db()

    print(f"MODE = {config.MODE}")
    if config.is_test_mode():
        print("TEST MODE ACTIVE")
        print("ALL EMAILS WILL BE REDIRECTED TO:", config.TEST_TO_EMAIL)

    records, skipped = load_companies(config.EXCEL_FILE, owner_filter=config.OWNER_FILTER)
    sync_companies_to_db(records)

    batch = select_batch(records)
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
            to_email = config.TEST_TO_EMAIL if config.is_test_mode() else item["email"]
            cc_list = config.active_cc_list()

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
                database.update_log_status(log_id, "DRAFT_CREATED", draft_message_id=draft_id)
                draft_results.append({"item": item, "log_id": log_id, "msg": msg,
                                       "to_email": to_email, "cc_list": cc_list, "ok": True})
                logger.info(f"Draft (.eml) created for {item['company_name']} -> {to_email}")
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
                database.update_rotation(d["item"]["company_key"], d["item"]["email"])
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
