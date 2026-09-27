import hmac
import math
import os
import re
import uuid
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

CATEGORIES = ("SLI", "EV", "LMT", "Stationary", "Industrial", "Consumer")
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


def init_database():
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
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
        r"\d{4}-(0[1-9]|1[0-2])", manufacture_date
    ):
        raise gr.Error(
            "Manufacturing Date must use YYYY-MM, for example 2026-09."
        )

    if granularity == "SKU" and not model_id:
        raise gr.Error("Model / SKU is required for SKU registrations.")

    if granularity == "Batch" and not batch_number:
        raise gr.Error(
            "Batch Number is required for Batch registrations."
        )

    if granularity == "Unit" and not serial_number:
        raise gr.Error(
            "Serial Number is required for Unit registrations."
        )

    battery_id = "MCBI-" + uuid.uuid4().hex[:16].upper()

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO batteries (
                        id, company, category, chemistry, weight,
                        capacity, capacity_unit, granularity, model_id,
                        batch_number, serial_number, country,
                        manufacture_date, status
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    battery_id, company, category, chemistry,
                    weight, capacity, capacity_unit, granularity,
                    model_id, batch_number, serial_number, country,
                    manufacture_date, status
                ))

                cur.execute("""
                    INSERT INTO battery_events (
                        battery_id, event_type, new_value
                    )
                    VALUES (%s, 'registered', %s)
                """, (battery_id, status))

    details = "\n".join((
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

    return battery_id, details, make_qr(battery_id)


def find_battery(battery_id):
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return "Please enter a Battery ID.", None

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
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

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id, company, category, chemistry, weight,
                    capacity, capacity_unit, granularity, model_id,
                    batch_number, serial_number, country,
                    manufacture_date, status, registered_at
                FROM batteries
                WHERE id = %s
            """, (battery_id,))
            record = cur.fetchone()

    if record is None:
        return "No battery record found for this ID."

    labels = (
        "Battery ID",
        "Company / Importer",
        "Category",
        "Chemistry",
        "Weight (kg)",
        "Capacity",
        "Capacity unit",
        "Registration level",
        "Model / SKU",
        "Batch number",
        "Serial number",
        "Manufacturing country",
        "Manufacturing date",
        "Lifecycle status",
        "Registered"
    )

    return "\n".join(
        f"{label}: {value if value is not None else '—'}"
        for label, value in zip(labels, record)
    )


def admin_list_batteries(admin_key):
    require_admin_key(admin_key)

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM batteries")
            total = cur.fetchone()[0]

            cur.execute("""
                SELECT id, company, category, model_id, registered_at
                FROM batteries
                ORDER BY registered_at DESC, id DESC
                LIMIT 50
            """)
            records = cur.fetchall()

    if not records:
        return "No batteries registered yet."

    rows = [
        f"Total registered: {total}. "
        f"Showing the newest {len(records)}:"
    ]

    rows.extend(
        f"{battery_id} | {company or '—'} | "
        f"{category or '—'} | {model_id or '—'} | {registered_at}"
        for battery_id, company, category, model_id, registered_at
        in records
    )

    return "\n".join(rows)


def change_status(battery_id, new_status, reason, admin_key):
    require_admin_key(admin_key)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id or new_status not in STATUSES:
        raise gr.Error(
            "Enter a Battery ID and a valid lifecycle status."
        )

    reason = required_text(reason, "Reason for status change")

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status
                    FROM batteries
                    WHERE id = %s
                    FOR UPDATE
                """, (battery_id,))
                row = cur.fetchone()

                if row is None:
                    raise gr.Error(
                        "No battery record found for this ID."
                    )

                old_status = row[0]

                if old_status == new_status:
                    return (
                        "Status is already set to this value. "
                        "No change was made."
                    )

                cur.execute("""
                    UPDATE batteries
                    SET status = %s
                    WHERE id = %s
                """, (new_status, battery_id))

                cur.execute("""
                    INSERT INTO battery_events (
                        battery_id, event_type,
                        old_value, new_value, reason
                    )
                    VALUES (
                        %s, 'status_changed', %s, %s, %s
                    )
                """, (
                    battery_id, old_status, new_status, reason
                ))

    return f"Status updated: {old_status} → {new_status}."


def admin_history(battery_id, admin_key):
    require_admin_key(admin_key)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return "Enter a Battery ID."

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    event_type, old_value, new_value,
                    reason, occurred_at
                FROM battery_events
                WHERE battery_id = %s
                ORDER BY id
            """, (battery_id,))
            events = cur.fetchall()

    if not events:
        return "No recorded events for this Battery ID."

    return "\n".join(
        f"{occurred_at}: {event_type} "
        f"({old or '—'} → {new or '—'})"
        + (f" — {reason}" if reason else "")
        for event_type, old, new, reason, occurred_at
        in events
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


def clear_battery_fields():
    return (
        None, None, None, None, None,
        None, "", "", "",
        "", "", "original"
    )


init_database()


CSS = """
.gradio-container { max-width: 880px !important; margin: 0 auto !important; }
#mcbi-header h1 { margin-bottom: 0.2em; }
#mcbi-footer { opacity: 0.75; font-size: 0.9em; }
"""


with gr.Blocks(title="MCBI EPR Portal") as demo:
    gr.Markdown(
        """
        # 🔋 MCBI EPR Portal
        **Монголын тойрог батарейн санаачилга · Mongolia Circular Battery Initiative**

        Батарей бүртгэх, таних, амьдралын мөчлөгийг хянах туршилтын систем ·
        Battery registration, identification and lifecycle tracking (pilot)
        """,
        elem_id="mcbi-header"
    )

    with gr.Tabs():

        # ---------- 1. Public lookup (default tab; QR links open here) ----------
        with gr.Tab("🔍 Хайх / Find", id="find"):
            gr.Markdown(
                "Батарейн ID-г оруулах эсвэл QR кодыг уншуулж нийтийн "
                "мэдээллийг харна. · Enter a Battery ID or scan its QR code."
            )
            lookup_id = gr.Textbox(
                label="Батарейн ID · Battery ID",
                placeholder="MCBI-8B675499..."
            )
            lookup_button = gr.Button("Хайх · Find", variant="primary")
            with gr.Row():
                lookup_result = gr.Textbox(
                    label="Нийтийн мэдээлэл · Public record",
                    lines=5,
                    interactive=False
                )
                lookup_qr = gr.Image(
                    label="QR код · QR code",
                    type="pil",
                    interactive=False,
                    height=220
                )

            lookup_button.click(
                fn=find_battery,
                inputs=lookup_id,
                outputs=[lookup_result, lookup_qr]
            )
            lookup_id.submit(
                fn=find_battery,
                inputs=lookup_id,
                outputs=[lookup_result, lookup_qr]
            )

        # ---------- 2. Registration (needs registration key) ----------
        with gr.Tab("➕ Бүртгэх / Register", id="register"):
            gr.Markdown(
                "Бүртгэл хийхэд бүртгэлийн түлхүүр шаардлагатай. · "
                "A registration key is required."
            )

            gr.Markdown("#### Үндсэн мэдээлэл · Basic information")
            with gr.Row():
                company = gr.Textbox(
                    label="Компани / Импортлогч · Company / Importer",
                    placeholder="Компанийн нэр · Company name"
                )
                category = gr.Dropdown(
                    list(CATEGORIES),
                    label="Ангилал · Category",
                    info="SLI → машины асаагуурын батарей · car starter battery"
                )
            with gr.Row():
                chemistry = gr.Dropdown(
                    list(CHEMISTRIES),
                    label="Химийн төрөл · Chemistry"
                )
                granularity = gr.Dropdown(
                    list(LEVELS),
                    label="Бүртгэлийн түвшин · Registration level",
                    info="SKU → загвар, Batch → багц, Unit → ширхэг"
                )
            with gr.Row():
                weight = gr.Number(label="Жин (кг) · Weight (kg)")
                capacity = gr.Number(label="Багтаамж · Capacity")
                capacity_unit = gr.Dropdown(
                    list(CAPACITY_UNITS),
                    label="Нэгж · Unit"
                )

            gr.Markdown("#### Таних мэдээлэл · Identification")
            with gr.Row():
                model_id = gr.Textbox(label="Загвар / SKU · Model / SKU")
                batch_number = gr.Textbox(label="Багцын дугаар · Batch number")
                serial_number = gr.Textbox(label="Серийн дугаар · Serial number")

            gr.Markdown("#### Үйлдвэрлэл · Manufacturing")
            with gr.Row():
                country = gr.Textbox(
                    label="Үйлдвэрлэсэн улс · Country of manufacture"
                )
                manufacture_date = gr.Textbox(
                    label="Үйлдвэрлэсэн огноо · Manufacturing date",
                    placeholder="YYYY-MM (2026-09)"
                )

            status = gr.Dropdown(
                list(STATUSES),
                value="original",
                label="Амьдралын мөчлөгийн төлөв · Lifecycle status"
            )
            registration_key = gr.Textbox(
                label="Бүртгэлийн түлхүүр · Registration key",
                type="password"
            )
            register_button = gr.Button(
                "Батарей бүртгэх · Register battery",
                variant="primary"
            )

            battery_id_output = gr.Textbox(
                label="Шинэ батарейн ID · New Battery ID",
                interactive=False
            )
            with gr.Row():
                record_output = gr.Textbox(
                    label="Бүртгэлийн дэлгэрэнгүй (нууц) · Record (private)",
                    lines=14,
                    interactive=False
                )
                qr_output = gr.Image(
                    label="QR код — батарейд наах · QR code for the label",
                    type="pil",
                    interactive=False,
                    height=260
                )

            battery_fields = [
                category, chemistry, weight, capacity, capacity_unit,
                granularity, model_id, batch_number, serial_number,
                country, manufacture_date, status
            ]

            register_button.click(
                fn=register_battery,
                inputs=[
                    company, category, chemistry, weight, capacity,
                    capacity_unit, granularity, model_id, batch_number,
                    serial_number, country, manufacture_date, status,
                    registration_key
                ],
                outputs=[battery_id_output, record_output, qr_output]
            ).success(
                # Clear the battery fields after a successful registration so
                # the next battery starts from an empty form. Company and the
                # registration key stay filled for the next entry.
                fn=clear_battery_fields,
                inputs=[],
                outputs=battery_fields
            )

            gr.Button(
                "🧹 Маягт цэвэрлэх · Clear form",
                variant="secondary"
            ).click(
                fn=clear_battery_fields,
                inputs=[],
                outputs=battery_fields
            )

        # ---------- 3. Admin ----------
        with gr.Tab("⚙️ Админ / Admin", id="admin"):
            gr.Markdown(
                "Түлхүүрээ бусадтай хуваалцах, нийтийн компьютер дээр "
                "үлдээхгүй байгаарай. · Do not share your key or leave it "
                "on a shared computer."
            )
            admin_key = gr.Textbox(
                label="Админ түлхүүр · Admin key",
                type="password"
            )

            recent_records = gr.Textbox(
                label="Сүүлийн бүртгэлүүд · Recent registrations",
                lines=10,
                interactive=False
            )
            gr.Button("Бүртгэлүүдийг харах · Show registrations").click(
                fn=admin_list_batteries,
                inputs=admin_key,
                outputs=recent_records
            )

            admin_id = gr.Textbox(label="Батарейн ID · Battery ID")

            with gr.Row():
                view_button = gr.Button("Дэлгэрэнгүй · Private record")
                history_button = gr.Button("Түүх · History")
            admin_result = gr.Textbox(
                label="Нууц мэдээлэл · Private record",
                lines=14,
                interactive=False
            )
            history_result = gr.Textbox(
                label="Бүртгэл ба төлөвийн түүх · History",
                lines=8,
                interactive=False
            )
            view_button.click(
                fn=admin_find_battery,
                inputs=[admin_id, admin_key],
                outputs=admin_result
            )
            history_button.click(
                fn=admin_history,
                inputs=[admin_id, admin_key],
                outputs=history_result
            )

            gr.Markdown("#### Төлөв өөрчлөх · Change status")
            with gr.Row():
                new_status = gr.Dropdown(
                    list(STATUSES),
                    label="Шинэ төлөв · New status"
                )
                status_reason = gr.Textbox(
                    label="Шалтгаан · Reason"
                )
            status_result = gr.Textbox(
                label="Үр дүн · Result",
                interactive=False
            )
            gr.Button("Төлөв шинэчлэх · Update status").click(
                fn=change_status,
                inputs=[admin_id, new_status, status_reason, admin_key],
                outputs=status_result
            )

    gr.Markdown(
        """
        ---
        **MCBI EPR Pilot — N-064** · Туршилтын хувилбар · Pilot prototype
        """,
        elem_id="mcbi-footer"
    )

    demo.load(
        fn=load_battery_from_url,
        inputs=[],
        outputs=[lookup_id, lookup_result, lookup_qr]
    )


port = int(os.getenv("PORT", "10000"))

demo.launch(
    server_name="0.0.0.0",
    server_port=port,
    ssr_mode=False,
    pwa=True,
    css=CSS,
    theme=gr.themes.Soft(primary_hue="emerald")
)
