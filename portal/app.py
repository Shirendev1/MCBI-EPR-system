import hmac
import math
import os
import re
import uuid
import time
from contextlib import closing
from datetime import datetime
from urllib.parse import quote

import gradio as gr
import psycopg2
import qrcode


DATABASE_URL = os.getenv("DATABASE_URL")
PORTAL_URL = os.getenv(
    "PORTAL_URL",
    "https://mcbi-epr-system.onrender.com"
).rstrip("/")

CATEGORIES = ("EV", "LMT", "Stationary", "Industrial", "Consumer")
CHEMISTRIES = ("LFP", "NMC", "NCA", "LCO", "LMO", "Lead-acid", "Other")
LEVELS = ("SKU", "Batch", "Unit")
CAPACITY_UNITS = ("Wh", "Ah")
STATUSES = ("original", "repurposed", "re-used", "remanufactured", "waste")


def require_admin_key(key):
    expected = os.getenv("REGISTRATION_KEY")
    if not expected or not hmac.compare_digest(key or "", expected):
        raise gr.Error("Admin key is missing or incorrect.")


def required_text(value, label):
    value = (value or "").strip()
    if not value:
        raise gr.Error(f"{label} is required.")
    return value


def positive_number(value, label):
    if (
        value is None
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise gr.Error(f"{label} must be a positive number.")
    return value


def make_qr(battery_id):
    url = f"{PORTAL_URL}/?battery_id={quote(battery_id, safe='')}"
    return qrcode.make(url).convert("RGB")


def init_database(retries: int = 4, initial_delay: float = 1.0, connect_timeout: int = 2):
    """Initialize the database schema, with a small bounded retry/backoff for
    transient DB unavailability.

    Parameters:
      - retries: total connection attempts
      - initial_delay: initial sleep (seconds) before retry; doubled on each retry
      - connect_timeout: timeout (seconds) passed to psycopg2.connect for each attempt
    """
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set DATABASE_URL (see .env.example) before starting the portal."
        )

    delay = initial_delay
    last_exception = None

    for attempt in range(1, retries + 1):
        try:
            # Attempt to connect with a short connection timeout for this attempt.
            with closing(psycopg2.connect(DATABASE_URL, connect_timeout=connect_timeout)) as conn:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS batteries (
                                id TEXT PRIMARY KEY,
                                company TEXT,
                                category TEXT,
                                chemistry TEXT,
                                weight DOUBLE PRECISION,
                                capacity DOUBLE PRECISION,
                                granularity TEXT,
                                model_id TEXT,
                                batch_number TEXT,
                                serial_number TEXT,
                                country TEXT,
                                manufacture_date TEXT,
                                status TEXT,
                                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)

                        cur.execute("""
                            CREATE TABLE IF NOT EXISTS battery_events (
                                id BIGSERIAL PRIMARY KEY,
                                battery_id TEXT NOT NULL REFERENCES batteries(id),
                                event_type TEXT NOT NULL,
                                old_value TEXT,
                                new_value TEXT,
                                reason TEXT,
                                occurred_at TIMESTAMPTZ NOT NULL
                                    DEFAULT CURRENT_TIMESTAMP
                            )
                        """)

                        cur.execute("""
                            ALTER TABLE batteries
                            ADD COLUMN IF NOT EXISTS capacity_unit TEXT
                        """)

                        cur.execute("""
                            ALTER TABLE battery_events
                            ADD COLUMN IF NOT EXISTS reason TEXT
                        """)
                        # --- End unchanged schema creation ---
            # Success: schema created and connection closed
            return
        except Exception as exc:
            last_exception = exc
            # If this was the last attempt, raise a clear runtime error
            if attempt == retries:
                raise RuntimeError(
                    f"Could not connect to the database after {retries} attempts. "
                    f"Last error: {exc}"
                ) from exc

            # Otherwise, log and wait before retrying
            print(
                f"Database connection attempt {attempt} failed: {exc!s}. "
                f"Retrying in {delay} second(s)..."
            )
            time.sleep(delay)
            delay = delay * 2  # exponential backoff


def register_battery(
    company,
    category,
    chemistry,
    weight,
    capacity,
    capacity_unit,
    granularity,
    model_id,
    batch_number,
    serial_number,
    country,
    manufacture_date,
    status,
    registration_key
):
    require_admin_key(registration_key)

    company = required_text(company, "Company / Importer")
    country = required_text(country, "Country of Manufacture")
    manufacture_date = required_text(
        manufacture_date, "Manufacturing Date"
    )
    model_id = (model_id or "").strip()
    batch_number = (batch_number or "").strip()
    serial_number = (serial_number or "").strip()

    if (
        category not in CATEGORIES
        or chemistry not in CHEMISTRIES
        or granularity not in LEVELS
    ):
        raise gr.Error(
            "Select a valid category, chemistry and registration level."
        )

    if status not in STATUSES or capacity_unit not in CAPACITY_UNITS:
        raise gr.Error(
            "Select a valid lifecycle status and capacity unit."
        )

    weight = positive_number(weight, "Weight")
    capacity = positive_number(capacity, "Capacity")

    if not re.fullmatch(
{