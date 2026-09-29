import hmac
import math
import os
import re
import tempfile
import uuid
from contextlib import closing
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
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

LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TIMEZONE", "Asia/Ulaanbaatar"))

# Fields an admin may correct after registration: label -> column
EDITABLE_FIELDS = {
    "Компани · Company": "company",
    "Ангилал · Category": "category",
    "Химийн төрөл · Chemistry": "chemistry",
    "Жин (кг) · Weight (kg)": "weight",
    "Багтаамж · Capacity": "capacity",
    "Нэгж · Capacity unit": "capacity_unit",
    "Бүртгэлийн түвшин · Registration level": "granularity",
    "Загвар / SKU · Model / SKU": "model_id",
    "Багцын дугаар · Batch number": "batch_number",
    "Серийн дугаар · Serial number": "serial_number",
    "Үйлдвэрлэсэн улс · Country": "country",
    "Үйлдвэрлэсэн огноо · Manufacturing date": "manufacture_date",
}


def local_time(value):
    """Show a stored timestamp in local (Ulaanbaatar) time."""
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")


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


def record_link(battery_id):
    """Public, shareable link that opens this battery's record."""
    return f"{PORTAL_URL}/?battery_id={quote(battery_id, safe='')}"


def make_qr(battery_id):
    return qrcode.make(record_link(battery_id)).convert("RGB")


QR_DIR = os.path.join(tempfile.gettempdir(), "mcbi_qr")


def save_qr_file(battery_id, image):
    """Save the QR image as a PNG so it can be downloaded by name."""
    os.makedirs(QR_DIR, exist_ok=True)
    path = os.path.join(QR_DIR, f"{battery_id}.png")
    image.save(path, format="PNG")
    return path


REQUIRED = " *"

# Which identification fields each registration level uses:
# field -> required?  Fields not listed are hidden and left empty.
LEVEL_FIELDS = {
    "SKU": {"model_id": True},
    "Batch": {"model_id": False, "batch_number": True},
    "Unit": {"model_id": False, "batch_number": False, "serial_number": True},
}

ID_LABELS = {
    "model_id": "Загвар / SKU · Model / SKU",
    "batch_number": "Багцын дугаар · Batch number",
    "serial_number": "Серийн дугаар · Serial number",
}

LEVEL_HINTS = {
    None: (
        "ℹ️ Эхлээд **бүртгэлийн түвшнээ** сонгоно уу — бөглөх талбарууд "
        "түүнээс хамаарна. · First choose a **registration level**; the "
        "fields below depend on it."
    ),
    "SKU": (
        "ℹ️ **SKU** — нэг загварыг бүхэлд нь бүртгэнэ. Зөвхөн загварын "
        "дугаар хэрэгтэй, **серийн дугаар хэрэггүй**. · Registers a whole "
        "battery model. Only the model / SKU is needed — **no serial number**."
    ),
    "Batch": (
        "ℹ️ **Batch** — нэг үйлдвэрлэлийн багцыг бүртгэнэ. **Багцын дугаар "
        "заавал**, загвар нь сонголтоор. · Registers one production batch. "
        "**Batch number is required**; model is optional."
    ),
    "Unit": (
        "ℹ️ **Unit** — нэг ширхэг батарейг бүртгэнэ. **Серийн дугаар "
        "заавал**, загвар ба багц сонголтоор. · Registers a single battery. "
        "**Serial number is required**; model and batch are optional."
    ),
}


def id_field_updates(level):
    """Show only the identification fields the chosen level needs."""
    fields = LEVEL_FIELDS.get(level, {})
    updates = []
    for name, label in ID_LABELS.items():
        if name in fields:
            updates.append(gr.update(
                visible=True,
                label=label + (REQUIRED if fields[name] else " (сонголтоор · optional)")
            ))
        else:
            updates.append(gr.update(visible=False, value=""))
    updates.append(LEVEL_HINTS.get(level, LEVEL_HINTS[None]))
    return updates


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

    # Drop identification values that this level does not use
    # (e.g. no serial number on an SKU registration).
    level_fields = LEVEL_FIELDS[granularity]
    if "batch_number" not in level_fields:
        batch_number = ""
    if "serial_number" not in level_fields:
        serial_number = ""

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
        f"Model / SKU: {model_id or '—'}",
        f"Batch number: {batch_number or '—'}",
        f"Serial number: {serial_number or '—'}",
        f"Manufacturing country: {country}",
        f"Manufacturing date: {manufacture_date}",
        f"Lifecycle status: {status}",
        f"Registered: {datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')}"
    ))

    qr = make_qr(battery_id)
    success = (
        f"### ✅ Бүртгэл амжилттай · Registration successful\n"
        f"Батарейн ID · Battery ID: **{battery_id}**  \n"
        f"QR кодыг татаж аваад батарейд наана уу. · "
        f"Download the QR code and attach it to the battery."
    )

    return (
        battery_id,
        details,
        qr,
        record_link(battery_id),
        gr.update(value=success, visible=True),
        gr.update(value=save_qr_file(battery_id, qr), visible=True),
        gr.update(visible=True),
    )


def reset_registration_results():
    """Hide the previous result so the next battery starts clean."""
    return (
        "", "", None, "",
        gr.update(value="", visible=False),
        gr.update(value=None, visible=False),
        gr.update(visible=False),
    )


def find_battery(battery_id):
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return "Please enter a Battery ID.", None, ""

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, category, chemistry, status
                FROM batteries
                WHERE id = %s
            """, (battery_id,))
            record = cur.fetchone()

    if record is None:
        return "No battery record found for this ID.", None, ""

    labels = (
        "Battery ID", "Category", "Chemistry", "Lifecycle status"
    )
    details = "\n".join(
        f"{label}: {value if value is not None else '—'}"
        for label, value in zip(labels, record)
    )

    return details, make_qr(record[0]), record_link(record[0])


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
                    manufacture_date, status,
                    registered_at::timestamptz
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

    values = list(record)
    values[-1] = local_time(values[-1])

    return "\n".join(
        f"{label}: {value if value is not None else '—'}"
        for label, value in zip(labels, values)
    )


def admin_list_batteries(admin_key):
    require_admin_key(admin_key)

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM batteries")
            total = cur.fetchone()[0]

            cur.execute("""
                SELECT id, company, category, model_id, status,
                       registered_at::timestamptz
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
        f"{category or '—'} | {model_id or '—'} | "
        f"{status or '—'} | {local_time(registered_at)}"
        for battery_id, company, category, model_id, status, registered_at
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
        f"{local_time(occurred_at)}: {event_type} "
        f"({old or '—'} → {new or '—'})"
        + (f" — {reason}" if reason else "")
        for event_type, old, new, reason, occurred_at
        in events
    )


def edit_battery(battery_id, field_label, new_value, reason, admin_key):
    require_admin_key(admin_key)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        raise gr.Error("Enter a Battery ID.")
    if field_label not in EDITABLE_FIELDS:
        raise gr.Error("Select the field to correct.")

    column = EDITABLE_FIELDS[field_label]
    reason = required_text(reason, "Reason")
    new_value = (new_value or "").strip()

    if column in ("company", "country"):
        new_value = required_text(new_value, field_label)
    elif column == "category" and new_value not in CATEGORIES:
        raise gr.Error("Category must be one of: " + ", ".join(CATEGORIES))
    elif column == "chemistry" and new_value not in CHEMISTRIES:
        raise gr.Error("Chemistry must be one of: " + ", ".join(CHEMISTRIES))
    elif column == "granularity" and new_value not in LEVELS:
        raise gr.Error("Registration level must be one of: " + ", ".join(LEVELS))
    elif column == "capacity_unit" and new_value not in CAPACITY_UNITS:
        raise gr.Error("Capacity unit must be one of: " + ", ".join(CAPACITY_UNITS))
    elif column in ("weight", "capacity"):
        try:
            number = float(new_value.replace(",", "."))
        except ValueError:
            raise gr.Error(f"{field_label} must be a number.")
        new_value = positive_number(number, field_label)
    elif column == "manufacture_date" and not re.fullmatch(
        r"\d{4}-(0[1-9]|1[0-2])", new_value
    ):
        raise gr.Error(
            "Manufacturing Date must use YYYY-MM, for example 2026-09."
        )

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                # column comes from the fixed EDITABLE_FIELDS whitelist
                cur.execute(
                    f"SELECT {column} FROM batteries WHERE id = %s FOR UPDATE",
                    (battery_id,)
                )
                row = cur.fetchone()
                if row is None:
                    raise gr.Error("No battery record found for this ID.")
                old_value = row[0]

                if str(old_value) == str(new_value):
                    return "No change: the new value is the same as the current one."

                cur.execute(
                    f"UPDATE batteries SET {column} = %s WHERE id = %s",
                    (new_value, battery_id)
                )
                cur.execute("""
                    INSERT INTO battery_events (
                        battery_id, event_type, old_value, new_value, reason
                    )
                    VALUES (%s, 'edited', %s, %s, %s)
                """, (
                    battery_id,
                    f"{column}: {old_value if old_value is not None else '—'}",
                    f"{column}: {new_value}",
                    reason
                ))

    return f"Updated {column}: {old_value} → {new_value}."


def load_battery_from_url(request: gr.Request):
    battery_id = (
        dict(request.query_params).get("battery_id", "")
        if request else ""
    )
    battery_id = battery_id.strip().upper()

    if not battery_id:
        return "", "", None, ""

    details, qr, link = find_battery(battery_id)
    return battery_id, details, qr, link


# Runs in the browser after a search: puts ?battery_id=... in the address
# bar so the page link always matches the record on screen.
SYNC_URL_JS = """
(batteryId, link) => {
    const url = new URL(window.location.href);
    const id = (batteryId || "").trim().toUpperCase();
    if (link && id) {
        url.searchParams.set("battery_id", id);
    } else {
        url.searchParams.delete("battery_id");
    }
    window.history.replaceState(null, "", url);
    return [];
}
"""

SCROLL_TOP_JS = "() => { window.scrollTo({top: 0, behavior: 'smooth'}); return []; }"


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
            lookup_link = gr.Textbox(
                label="Бүртгэлийн холбоос · Record link",
                info="Хуулах товчоор холбоосыг хуулж бусадтай хуваалцана. · "
                     "Use the copy button to share this record.",
                interactive=False,
                buttons=["copy"]
            )

            for trigger in (lookup_button.click, lookup_id.submit):
                trigger(
                    fn=find_battery,
                    inputs=lookup_id,
                    outputs=[lookup_result, lookup_qr, lookup_link]
                ).then(
                    fn=None,
                    inputs=[lookup_id, lookup_link],
                    js=SYNC_URL_JS
                )

        # ---------- 2. Registration (needs registration key) ----------
        with gr.Tab("➕ Бүртгэх / Register", id="register"):
            gr.Markdown(
                "Бүртгэл хийхэд бүртгэлийн түлхүүр шаардлагатай. · "
                "A registration key is required.  \n"
                "**\\*** — заавал бөглөх талбар · required field"
            )

            gr.Markdown("#### Үндсэн мэдээлэл · Basic information")
            with gr.Row():
                company = gr.Textbox(
                    label="Компани / Импортлогч · Company / Importer" + REQUIRED,
                    placeholder="Компанийн нэр · Company name"
                )
                category = gr.Dropdown(
                    list(CATEGORIES),
                    value=None,
                    label="Ангилал · Category" + REQUIRED,
                    info="SLI → машины асаагуурын батарей · car starter battery"
                )
            with gr.Row():
                chemistry = gr.Dropdown(
                    list(CHEMISTRIES),
                    value=None,
                    label="Химийн төрөл · Chemistry" + REQUIRED
                )
                granularity = gr.Dropdown(
                    list(LEVELS),
                    value=None,
                    label="Бүртгэлийн түвшин · Registration level" + REQUIRED,
                    info="SKU → загвар, Batch → багц, Unit → ширхэг"
                )
            with gr.Row():
                weight = gr.Number(label="Жин (кг) · Weight (kg)" + REQUIRED)
                capacity = gr.Number(label="Багтаамж · Capacity" + REQUIRED)
                capacity_unit = gr.Dropdown(
                    list(CAPACITY_UNITS),
                    value=None,
                    label="Нэгж · Unit" + REQUIRED
                )

            gr.Markdown("#### Таних мэдээлэл · Identification")
            level_hint = gr.Markdown(LEVEL_HINTS[None])
            with gr.Row():
                model_id = gr.Textbox(
                    label=ID_LABELS["model_id"], visible=False
                )
                batch_number = gr.Textbox(
                    label=ID_LABELS["batch_number"], visible=False
                )
                serial_number = gr.Textbox(
                    label=ID_LABELS["serial_number"], visible=False
                )

            granularity.change(
                fn=id_field_updates,
                inputs=granularity,
                outputs=[model_id, batch_number, serial_number, level_hint]
            )

            gr.Markdown("#### Үйлдвэрлэл · Manufacturing")
            with gr.Row():
                country = gr.Textbox(
                    label="Үйлдвэрлэсэн улс · Country of manufacture" + REQUIRED
                )
                manufacture_date = gr.Textbox(
                    label="Үйлдвэрлэсэн огноо · Manufacturing date" + REQUIRED,
                    placeholder="YYYY-MM (2026-09)"
                )

            status = gr.Dropdown(
                list(STATUSES),
                value="original",
                label="Амьдралын мөчлөгийн төлөв · Lifecycle status" + REQUIRED
            )
            registration_key = gr.Textbox(
                label="Бүртгэлийн түлхүүр · Registration key" + REQUIRED,
                type="password"
            )
            register_button = gr.Button(
                "Батарей бүртгэх · Register battery",
                variant="primary"
            )

            success_banner = gr.Markdown(visible=False)
            battery_id_output = gr.Textbox(
                label="Шинэ батарейн ID · New Battery ID",
                interactive=False,
                buttons=["copy"]
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
            register_link = gr.Textbox(
                label="Бүртгэлийн холбоос · Record link",
                interactive=False,
                buttons=["copy"]
            )
            with gr.Row():
                qr_download = gr.DownloadButton(
                    "⬇️ QR код татах · Download QR code",
                    variant="primary",
                    visible=False
                )
                register_another = gr.Button(
                    "➕ Өөр батарей бүртгэх · Register another battery",
                    variant="secondary",
                    visible=False
                )

            battery_fields = [
                category, chemistry, weight, capacity, capacity_unit,
                granularity, model_id, batch_number, serial_number,
                country, manufacture_date, status
            ]
            result_outputs = [
                battery_id_output, record_output, qr_output, register_link,
                success_banner, qr_download, register_another
            ]

            register_button.click(
                fn=register_battery,
                inputs=[
                    company, category, chemistry, weight, capacity,
                    capacity_unit, granularity, model_id, batch_number,
                    serial_number, country, manufacture_date, status,
                    registration_key
                ],
                outputs=result_outputs
            ).success(
                # Clear the battery fields after a successful registration so
                # the same battery is not registered twice by accident.
                # Company and the registration key stay filled.
                fn=clear_battery_fields,
                inputs=[],
                outputs=battery_fields
            )

            # "Register another": hide the last result and go back to the top
            register_another.click(
                fn=reset_registration_results,
                inputs=[],
                outputs=result_outputs
            ).then(
                fn=clear_battery_fields,
                inputs=[],
                outputs=battery_fields
            ).then(fn=None, js=SCROLL_TOP_JS)

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
                "#### Бүртгэл засах · Correct a record\n"
                "Алдаатай бичсэн талбарыг засна. Хуучин утга түүхэнд "
                "хадгалагдана. · Fix a mistyped field; the old value is "
                "kept in the history."
            )
            with gr.Row():
                edit_field = gr.Dropdown(
                    list(EDITABLE_FIELDS),
                    label="Засах талбар · Field"
                )
                edit_value = gr.Textbox(
                    label="Зөв утга · Correct value"
                )
            edit_reason = gr.Textbox(
                label="Шалтгаан · Reason",
                placeholder="Жишээ нь: Багтаамжийг буруу бичсэн"
            )
            edit_result = gr.Textbox(
                label="Үр дүн · Result",
                interactive=False
            )
            gr.Button("Засвар хадгалах · Save correction").click(
                fn=edit_battery,
                inputs=[admin_id, edit_field, edit_value, edit_reason, admin_key],
                outputs=edit_result
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
        outputs=[lookup_id, lookup_result, lookup_qr, lookup_link]
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
