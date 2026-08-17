"""
mail_client.py
===============
SMTP-only send for Microsoft 365 (username + app-password / account password).

WHY IMAP WAS REMOVED:
  Many institutional Microsoft 365 tenants (including NMIMS) disable IMAP
  access for student/staff accounts to prevent account compromise. Attempting
  IMAP auth on such accounts raises an "AUTHENTICATE failed" error and — worse
  — every failed IMAP login attempt is logged by Microsoft's identity
  protection service and can trigger a temporary account lock after a few
  retries.

  The previous code crashed at the IMAP step before any email was sent at all.

REPLACEMENT DRAFT MECHANISM (local .eml files):
  Instead of uploading drafts to Outlook via IMAP, this module saves each
  built message as a plain .eml file inside the "drafts/" subfolder of the
  data directory. You can open these with any mail client (Thunderbird,
  Outlook import, etc.) to inspect the exact content before confirming the
  send. The "draft_id" stored in the DB is the path to that .eml file.

ANTI-BLOCKING MEASURES:
  1. Random inter-send delay (SEND_DELAY_MIN - SEND_DELAY_MAX seconds).
  2. SMTP session reuse - one STARTTLS connection for the whole batch.
  3. Automatic SMTP reconnect if the server drops the connection mid-batch.
  4. Soft retry (up to SMTP_RETRY_LIMIT attempts) with back-off on transient
     failures, so a single flaky send does not abort the whole run.

SECURITY:
  The password is requested via getpass() at the start of a run and lives only
  in this process's memory. It is never written to disk, never logged, and
  never included in the SQLite database.
"""

import os
import random
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import make_msgid

import config
from logger_setup import get_logger

logger = get_logger()

# ------------------------------------------------------------------
# Tunables
# ------------------------------------------------------------------
SEND_DELAY_MIN = 4      # seconds to wait between successive sends (min)
SEND_DELAY_MAX = 9      # seconds to wait between successive sends (max)
SMTP_RETRY_LIMIT = 3    # max attempts per individual send
SMTP_RETRY_BACKOFF = 5  # base seconds to sleep before each retry


class MailSession:
    """Holds one authenticated SMTP session for the duration of a run.

    IMAP is intentionally absent — see module docstring.
    """

    def __init__(self, password):
        self._password = password
        self._smtp = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self):
        """Open and authenticate the SMTP connection."""
        logger.info("Connecting to Microsoft 365 SMTP...")
        self._smtp = self._new_smtp_connection()
        logger.info("SMTP authentication successful.")

    def _new_smtp_connection(self):
        """Create a fresh authenticated SMTP connection and return it."""
        smtp = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30)
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(config.SENDER_EMAIL, self._password)
        return smtp

    def _ensure_smtp(self):
        """Reconnect SMTP if the server has dropped the connection."""
        try:
            status = self._smtp.noop()   # returns (250, b'2.0.0 OK')
            if status[0] != 250:
                raise smtplib.SMTPServerDisconnected("NOOP returned non-250")
        except Exception:
            logger.warning("SMTP connection lost - reconnecting...")
            self._smtp = self._new_smtp_connection()
            logger.info("SMTP reconnected successfully.")

    def close(self):
        try:
            if self._smtp:
                self._smtp.quit()
        except Exception:
            pass
        self._smtp = None

    # ------------------------------------------------------------------
    # Message construction
    # ------------------------------------------------------------------

    def build_message(self, to_email, subject, html_body, plaintext_body, cc_list):
        msg = EmailMessage()
        msg["From"] = config.SENDER_EMAIL
        msg["To"] = to_email
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)
        msg["Subject"] = subject
        msg["Message-ID"] = make_msgid()
        msg.set_content(plaintext_body)
        msg.add_alternative(html_body, subtype="html")
        return msg

    # ------------------------------------------------------------------
    # Local-file draft (replaces IMAP APPEND)
    # ------------------------------------------------------------------

    def create_draft(self, msg, company_name: str = "") -> str:
        """Save the message as a local .eml file in the drafts directory.

        Returns the absolute path of the .eml file, which is stored as the
        draft_id in the database so you can locate/inspect it later.

        Raises RuntimeError if the file cannot be written.
        """
        drafts_dir = os.path.join(config.data_dir(), "drafts")
        os.makedirs(drafts_dir, exist_ok=True)

        # Sanitise company name for use as a filename
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in company_name)
        safe_name = safe_name.strip().replace(" ", "_")[:60] or "draft"
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_name}.eml"
        filepath = os.path.join(drafts_dir, filename)

        try:
            with open(filepath, "wb") as fh:
                fh.write(msg.as_bytes())
        except OSError as exc:
            raise RuntimeError(f"Could not write draft .eml to {filepath}: {exc}") from exc

        logger.info(f"Draft saved locally: {filepath}")
        return filepath

    # ------------------------------------------------------------------
    # Send with retry + anti-blocking delay
    # ------------------------------------------------------------------

    def send(self, msg: EmailMessage, to_email: str, cc_list: list,
             inter_send_delay: bool = True) -> str:
        """Send the message via SMTP with retry logic.

        Parameters
        ----------
        msg:               The built EmailMessage.
        to_email:          Primary recipient address.
        cc_list:           List of CC addresses (may be empty).
        inter_send_delay:  If True, sleep a random interval before sending.
                           Pass False for the very first email in a batch.

        Returns the Message-ID string on success, raises on final failure.
        """
        all_recipients = [to_email] + list(cc_list)

        if inter_send_delay:
            delay = random.uniform(SEND_DELAY_MIN, SEND_DELAY_MAX)
            logger.info(f"Waiting {delay:.1f}s before next send (anti-rate-limit)...")
            time.sleep(delay)

        last_exc = None
        for attempt in range(1, SMTP_RETRY_LIMIT + 1):
            try:
                self._ensure_smtp()
                self._smtp.send_message(msg, to_addrs=all_recipients)
                logger.info(f"Email sent to {to_email} (attempt {attempt})")
                return msg["Message-ID"]
            except smtplib.SMTPRecipientsRefused as exc:
                # Hard rejection of ALL recipients — no point retrying.
                raise RuntimeError(
                    f"All recipients refused by server: {exc.recipients}"
                ) from exc
            except (smtplib.SMTPException, OSError) as exc:
                last_exc = exc
                if attempt < SMTP_RETRY_LIMIT:
                    wait = SMTP_RETRY_BACKOFF * attempt
                    logger.warning(
                        f"Send attempt {attempt} failed ({exc}); retrying in {wait}s..."
                    )
                    time.sleep(wait)
                    try:
                        self._smtp.quit()
                    except Exception:
                        pass
                    self._smtp = self._new_smtp_connection()

        raise RuntimeError(
            f"All {SMTP_RETRY_LIMIT} send attempts failed. Last error: {last_exc}"
        ) from last_exc
