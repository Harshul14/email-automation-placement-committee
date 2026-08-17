"""
logger_setup.py
================
Central logging. Never logs passwords, tokens, or secrets — only
operational events (what company, what recipient, what status).
"""

import logging
import os
from datetime import datetime

import config


def get_logger(name="campaign"):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured (avoid duplicate handlers)

    logger.setLevel(logging.INFO)

    log_file = os.path.join(
        config.log_dir(), f"campaign_{datetime.now().strftime('%Y-%m-%d')}.log"
    )
    error_file = os.path.join(config.log_dir(), "errors.log")

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.INFO)

    error_handler = logging.FileHandler(error_file, encoding="utf-8")
    error_handler.setFormatter(fmt)
    error_handler.setLevel(logging.ERROR)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)

    return logger
