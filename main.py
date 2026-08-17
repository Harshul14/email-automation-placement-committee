"""
main.py
=======
Colab entrypoint. Run this after uploading/placing the Excel file next
to this script (or updating config.EXCEL_FILE with the correct path)
and putting the DOCX template at templates/email_template.docx.

Typical Colab usage:

    from google.colab import drive
    drive.mount('/content/drive')

    !python main.py

Or, inside a notebook cell:

    import main
    main.run_campaign()
"""

import os
import sys

import config
import database


def _try_mount_drive():
    try:
        from google.colab import drive  # noqa
        if not os.path.isdir("/content/drive"):
            drive.mount("/content/drive")
            print("Google Drive mounted — campaign history will persist across sessions.")
    except ImportError:
        print("Not running in Colab (or google.colab unavailable) — using local data/ and logs/.")


def run_campaign():
    _try_mount_drive()
    database.init_db()
    import campaign_runner
    campaign_runner.run()


def show_failed_schedules():
    _try_mount_drive()
    database.init_db()
    import campaign_runner
    campaign_runner.view_failed_schedules()


def export_report():
    _try_mount_drive()
    database.init_db()
    import campaign_runner
    campaign_runner.export_report()


if __name__ == "__main__":
    if "--failed" in sys.argv:
        show_failed_schedules()
    elif "--export" in sys.argv:
        export_report()
    else:
        run_campaign()
