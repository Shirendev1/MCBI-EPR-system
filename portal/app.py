import gradio as gr
import uuid
from datetime import datetime
import os
import hmac
import math
import re
from contextlib import closing
import psycopg2
import qrcode
from urllib.parse import quote

DATABASE_URL = os.getenv("DATABASE_URL")
PORTAL_URL = os.getenv(
    "PORTAL_URL", "https://mcbi-epr-system.onrender.com"
).rstrip("/")

STATUSES = ("original", "repurposed", "re-used", "remanufactured", "waste")
CATEGORIES = ("EV", "LMT", "Stationary", "Industrial", "Consumer")
CHEMISTRIES = ("LFP", "NMC", "NCA", "LCO", "LMO", "Lead-acid", "Other")
LEVELS = ("SKU", "Batch", "Unit")
CAPACITY_UNITS = ("Wh", "Ah")


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


def init_database():
    with closing(psycopg2.connect(DATABASE_URL)) as conn, conn, conn.cursor() as cur:
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
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS battery_events (
                id BIGSERIAL PRIMARY KEY,
                battery_id TEXT NOT NULL REFERENCES batteries(id),
                event_type TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute(
            "ALTER TABLE batteries ADD COLUMN IF NOT EXISTS capacity_unit TEXT"
        )
        cur.execute(
            "ALTER TABLE battery_events ADD COLUMN IF NOT EXISTS reason TEXT"
        )


init_database()


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
    manufacture_date = required_text(manufacture_date, "Manufacturing Date")
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
        raise gr.Error("Select a valid lifecycle status and capacity unit.")

    weight = positive_number(weight, "Weight")
    capacity = positive_number(capacity, "Capacity")

    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", manufacture_date):
        raise gr.Error(
            "Manufacturing Date must use YYYY-MM, for example 2026-09."
        )

    if granularity == "SKU" and not model_id:
        raise gr.Error("Model / SKU is required for SKU registrations.")

    if granularity == "Batch" and not batch_number:
        raise gr.Error("Batch Number is required for Batch registrations.")

    if granularity == "Unit" and not serial_number:
        raise gr.Error("Serial Number is required for Unit registrations.")

    battery_id = "MCBI-" + uuid.uuid4().hex[:16].upper()

    with closing(psycopg2.connect(DATABASE_URL)) as conn, conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO batteries (
                id, company, category, chemistry, weight, capacity,
                capacity_unit, granularity, model_id, batch_number,
                serial_number, country, manufacture_date, status
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            battery_id, company, category, chemistry, weight, capacity,
            capacity_unit, granularity, model_id, batch_number,
            serial_number, country, manufacture_date, status
        ))

        cur.execute("""
            INSERT INTO battery_events (
                battery_id, event_type, new_value
            )
            VALUES (%s, 'registered', %s)
        """, (battery_id, status))

    result = "\n".join((
        f"Battery ID: {battery_id}",
        f"Company / Importer: {company}",
        f"Category: {category}",
        f"Chemistry: {chemistry}",
        f"Weight (kg): {weight}",
        f"Capacity ({capacity_unit}): {capacity}",
        f"Registration level: {granularity}",
        f"Model / SKU: {model_id}",
        f"Batch number: {batch_number}",
        f"Serial number: {serial_number}",
        f"Manufacturing country: {country}",
        f"Manufacturing date: {manufacture_date}",
        f"Lifecycle status: {status}",
        f"Registered: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ))

    return battery_id, result, make_qr(battery_id)


def find_battery(battery_id):
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return "Please enter a Battery ID.", None

    with closing(psycopg2.connect(DATABASE_URL)) as conn, conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, category, chemistry, status
            FROM batteries
            WHERE id = %s
        """, (battery_id,))
        record = cur.fetchone()

    if record is None:
        return "No battery record found for this ID.", None

    labels = (
        "Battery ID", "Category", "Chemistry", "Lifecycle status"
    )
    details = "\n".join(
        f"{label}: {value if value is not None else '—'}"
        for label, value in zip(labels, record)
    )
    return details, make_qr(record[0])


def admin_find_battery(battery_id, admin_key):
    require_admin_key(admin_key)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return "Enter a Battery ID."

    with closing(psycopg2.connect(DATABASE_URL)) as conn, conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, company, category, chemistry, weight, capacity,
                   capacity_unit, granularity, model_id, batch_number,
                   serial_number, country, manufacture_date, status,
                   registered_at
            FROM batteries
            WHERE id = %s
        """, (battery_id,))
        record = cur.fetchone()

    if record is None:
        return "No battery record found for this ID."

    labels = (
        "Battery ID", "Company / Importer", "Category", "Chemistry",
        "Weight (kg)", "Capacity", "Capacity unit",
        "Registration level", "Model / SKU", "Batch number",
        "Serial number", "Manufacturing country",
        "Manufacturing date", "Lifecycle status", "Registered"
    )

    return "\n".join(
        f"{label}: {value if value is not None else '—'}"
        for label, value in zip(labels, record)
    )


def change_status(battery_id, new_status, reason, admin_key):
    require_admin_key(admin_key)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id or new_status not in STATUSES:
        raise gr.Error("Enter a Battery ID and a valid lifecycle status.")

    reason = required_text(reason, "Reason for status change")

    with closing(psycopg2.connect(DATABASE_URL)) as conn, conn, conn.cursor() as cur:
        cur.execute(
            "SELECT status FROM batteries WHERE id = %s FOR UPDATE",
            (battery_id,)
        )
        row = cur.fetchone()

        if row is None:
            raise gr.Error("No battery record found for this ID.")

        old_status = row[0]
        if old_status == new_status:
            return "Status is already set to this value. No change was made."

        cur.execute(
            "UPDATE batteries SET status = %s WHERE id = %s",
            (new_status, battery_id)
        )

        cur.execute("""
            INSERT INTO battery_events (
                battery_id, event_type, old_value, new_value, reason
            )
            VALUES (%s, 'status_changed', %s, %s, %s)
        """, (battery_id, old_status, new_status, reason))

    return f"Status updated: {old_status} → {new_status}."


def admin_history(battery_id, admin_key):
    require_admin_key(admin_key)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return "Enter a Battery ID."

    with closing(psycopg2.connect(DATABASE_URL)) as conn, conn, conn.cursor() as cur:
        cur.execute("""
            SELECT event_type, old_value, new_value, reason, occurred_at
            FROM battery_events
            WHERE battery_id = %s
            ORDER BY id
        """, (battery_id,))
        events = cur.fetchall()

    if not events:
        return "No recorded events for this Battery ID."

    return "\n".join(
        f"{occurred_at}: {event_type} ({old or '—'} → {new or '—'})"
        + (f" — {reason}" if reason else "")
        for event_type, old, new, reason, occurred_at in events
    )


def load_battery_from_url(request: gr.Request):
    battery_id = (
        dict(request.query_params).get("battery_id", "")
        if request else ""
    )
    battery_id = battery_id.strip().upper()

    if not battery_id:
        return "", "", None

    details, qr = find_battery(battery_id)
    return battery_id, details, qr


with gr.Blocks(title="MCBI EPR Pilot Portal") as demo:
    gr.Markdown("""
    # 🔋 MCBI EPR Pilot Portal
    **Mongolia Circular Battery Initiative**

    Battery registration • Identification • Lifecycle tracking

    ### Battery Registration
    """)

    with gr.Row():
        company = gr.Textbox(
            label="Company / Importer",
            placeholder="Company name"
        )
        category = gr.Dropdown(
            list(CATEGORIES),
            label="Battery Category"
        )

    with gr.Row():
        chemistry = gr.Dropdown(
            list(CHEMISTRIES),
            label="Chemistry"
        )
        granularity = gr.Dropdown(
            list(LEVELS),
            label="Registration Level"
        )

    with gr.Row():
        weight = gr.Number(label="Weight (kg)")
        capacity = gr.Number(label="Capacity")
        capacity_unit = gr.Dropdown(
            list(CAPACITY_UNITS),
            label="Capacity unit"
        )

    gr.Markdown("### Identification")

    with gr.Row():
        model_id = gr.Textbox(label="Model / SKU")
        batch_number = gr.Textbox(label="Batch Number")
        serial_number = gr.Textbox(label="Serial Number")

    gr.Markdown("### Manufacturing")

    with gr.Row():
        country = gr.Textbox(label="Country of Manufacture")
        manufacture_date = gr.Textbox(
            label="Manufacturing Date",
            placeholder="YYYY-MM"
        )

    status = gr.Dropdown(
        list(STATUSES),
        value="original",
        label="Lifecycle Status"
    )

    registration_key = gr.Textbox(
        label="Registration key (admin only)",
        type="password"
    )
    register_button = gr.Button("Register Battery")

    battery_id_output = gr.Textbox(
        label="Generated Battery ID",
        interactive=False
    )
    record_output = gr.Textbox(
        label="New battery record (private)",
        lines=15,
        interactive=False
    )
    gr.Markdown(
        "Scan the QR code to open this battery's limited public record."
    )
    qr_output = gr.Image(
        label="Battery ID QR Code",
        type="pil",
        interactive=False
    )

    register_button.click(
        fn=register_battery,
        inputs=[
            company, category, chemistry, weight, capacity,
            capacity_unit, granularity, model_id, batch_number,
            serial_number, country, manufacture_date, status,
            registration_key
        ],
        outputs=[
            battery_id_output, record_output, qr_output
        ]
    )

    gr.Markdown("### Find a Registered Battery")

    lookup_id = gr.Textbox(
        label="Battery ID",
        placeholder="MCBI-8B675499"
    )
    lookup_button = gr.Button("Find Battery")
    lookup_result = gr.Textbox(
        label="Public Battery Record",
        lines=5,
        interactive=False
    )
    lookup_qr = gr.Image(
        label="Stored Battery ID QR Code",
        type="pil",
        interactive=False
    )

    lookup_button.click(
        fn=find_battery,
        inputs=lookup_id,
        outputs=[lookup_result, lookup_qr]
    )

    demo.load(
        fn=load_battery_from_url,
        inputs=[],
        outputs=[lookup_id, lookup_result, lookup_qr]
    )

    with gr.Accordion(
        "Admin: private record and lifecycle history",
        open=False
    ):
        gr.Markdown(
            "Use your existing registration key. Do not share it "
            "or leave it on a shared computer."
        )
        admin_id = gr.Textbox(label="Battery ID")
        admin_key = gr.Textbox(
            label="Admin key",
            type="password"
        )
        admin_result = gr.Textbox(
            label="Private battery record",
            lines=15,
            interactive=False
        )

        gr.Button("View private record").click(
            fn=admin_find_battery,
            inputs=[admin_id, admin_key],
            outputs=admin_result
        )

        new_status = gr.Dropdown(
            list(STATUSES),
            label="New lifecycle status"
        )
        status_reason = gr.Textbox(
            label="Reason for status change"
        )
        status_result = gr.Textbox(
            label="Update result",
            interactive=False
        )

        gr.Button("Update status").click(
            fn=change_status,
            inputs=[
                admin_id, new_status, status_reason, admin_key
            ],
            outputs=status_result
        )

        history_result = gr.Textbox(
            label="Registration and status history",
            lines=8,
            interactive=False
        )

        gr.Button("View history").click(
            fn=admin_history,
            inputs=[admin_id, admin_key],
            outputs=history_result
        )

    gr.Markdown("""
    ---
    **MCBI EPR Pilot — N-064**

    Prototype for testing battery identification and EPR data flows.
    """)


demo.launch(
    server_name="0.0.0.0",
    server_port=10000,
    ssr_mode=False
)
