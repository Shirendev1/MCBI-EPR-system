import base64
import hmac
import html
import io
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

# Mongolian display names. The database keeps the English codes.
CATEGORY_MN = {
    "SLI": "Асаагуурын батарей (SLI)",
    "EV": "Цахилгаан тээврийн хэрэгслийн (EV)",
    "LMT": "Хөнгөн тээврийн (LMT)",
    "Stationary": "Суурин хадгалалтын",
    "Industrial": "Үйлдвэрийн",
    "Consumer": "Зөөврийн / өргөн хэрэглээний",
}
CHEMISTRY_MN = {"Lead-acid": "Хар тугалга-хүчил", "Other": "Бусад"}
STATUS_MN = {
    "original": "Шинэ",
    "repurposed": "Өөр зориулалтад шилжүүлсэн",
    "re-used": "Дахин ашигласан",
    "remanufactured": "Дахин үйлдвэрлэсэн",
    "waste": "Хаягдал",
}
LEVEL_MN = {"SKU": "Загвараар", "Batch": "Багцаар", "Unit": "Ширхэгээр"}

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


def require_admin_key(key, kind="admin"):
    expected = os.getenv("REGISTRATION_KEY")
    if not expected or not hmac.compare_digest(key or "", expected):
        if kind == "registration":
            raise gr.Error(
                "Бүртгэлийн түлхүүр хоосон эсвэл буруу байна. · "
                "Registration key is missing or incorrect."
            )
        raise gr.Error(
            "Админ түлхүүр хоосон эсвэл буруу байна. · "
            "Admin key is missing or incorrect."
        )


def required_text(value, label):
    value = (value or "").strip()
    if not value:
        raise gr.Error(f"{label}: заавал бөглөнө. · {label} is required.")
    return value


def positive_number(value, label):
    if (
        value is None
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise gr.Error(
            f"{label}: 0-ээс их тоо оруулна уу. · "
            f"{label} must be a positive number."
        )
    return value


def record_link(battery_id):
    """Public, shareable link that opens this battery's record."""
    return f"{PORTAL_URL}/?battery_id={quote(battery_id, safe='')}"


def make_qr(battery_id):
    return qrcode.make(record_link(battery_id), border=2).convert("RGB")


def image_data_uri(image):
    """Embed a PIL image in HTML as a PNG data URI."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")


QR_DIR = os.path.join(tempfile.gettempdir(), "mcbi_qr")


def save_qr_file(battery_id, image):
    """Save the QR image as a PNG so it can be downloaded by name."""
    os.makedirs(QR_DIR, exist_ok=True)
    path = os.path.join(QR_DIR, f"{battery_id}.png")
    image.save(path, format="PNG")
    return path


# Which identification fields each registration level uses:
# field -> required?  Fields not listed are hidden and left empty.
LEVEL_FIELDS = {
    "SKU": {"model_id": True},
    "Batch": {"model_id": False, "batch_number": True},
    "Unit": {"model_id": False, "batch_number": False, "serial_number": True},
}

ID_LABELS = {
    "model_id": "Загвар / SKU",
    "batch_number": "Багцын дугаар",
    "serial_number": "Серийн дугаар",
}
ID_INFO = {
    "model_id": "Model / SKU",
    "batch_number": "Batch number",
    "serial_number": "Serial number",
}

LEVEL_HINTS = {
    None: (
        "Эхлээд **бүртгэлийн түвшнээ** сонгоно уу. Доорх талбарууд "
        "түүнээс хамаарна."
    ),
    "SKU": (
        "**Загвараар** — нэг загварыг бүхэлд нь бүртгэнэ. Зөвхөн загварын "
        "дугаар хэрэгтэй."
    ),
    "Batch": (
        "**Багцаар** — нэг үйлдвэрлэлийн багцыг бүртгэнэ. Багцын дугаар "
        "заавал, загвар нь сонголтоор."
    ),
    "Unit": (
        "**Ширхэгээр** — нэг ширхэг батарейг бүртгэнэ. Серийн дугаар "
        "заавал, загвар ба багц сонголтоор."
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
                label=label + ("" if fields[name] else " (сонголтоор)")
            ))
        else:
            updates.append(gr.update(visible=False, value=""))
    updates.append(LEVEL_HINTS.get(level, LEVEL_HINTS[None]))
    return updates


# ---------- HTML building blocks (all user text is escaped) ----------

def esc(value):
    if value is None or value == "":
        return "—"
    return html.escape(str(value))


def fmt_number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def lifecycle_html(status):
    stage = {
        "original": 0, "re-used": 1, "repurposed": 1,
        "remanufactured": 1, "waste": 2,
    }.get(status, 0)
    steps = (
        "Шинэ · ашиглалтад",
        "Дахин ашиглалт / хоёр дахь амьдрал",
        "Цуглуулалт ба дахин боловсруулалт",
    )
    items = []
    for index, text in enumerate(steps):
        state = (
            "done" if index < stage
            else "current" if index == stage
            else "todo"
        )
        items.append(f'<li class="mcbi-step-{state}"><span></span>{text}</li>')
    return '<ol class="mcbi-life">' + "".join(items) + "</ol>"


WASTE_NOTE = """
<div class="mcbi-note">
  <svg width="26" height="30" viewBox="0 0 30 34" aria-hidden="true">
    <path d="M8 9h14l-1.5 19h-11z" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linejoin="round"/>
    <path d="M6 9h18M12 9V6h6v3" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round"/>
    <path d="M3 4l24 27M27 4L3 31" stroke="currentColor" stroke-width="2"
          stroke-linecap="round"/>
  </svg>
  <div><strong>Энгийн хогтой хамт хаяж болохгүй</strong>
  Ашиглалтаас гарсан батарейг цуглуулах цэгт хүлээлгэн өгнө.
  · Do not dispose of with household waste.</div>
</div>
"""


def public_card(record):
    battery_id, category, chemistry, status, registered_at = record
    qr = image_data_uri(make_qr(battery_id))
    registered = local_time(registered_at)
    return f"""
<div class="mcbi-passport">
  <div class="mcbi-passport-dark">
    <span class="mcbi-eyebrow">БАТАРЕЙН ПАСПОРТ · BATTERY PASSPORT</span>
    <span class="mcbi-big">{esc(CHEMISTRY_MN.get(chemistry, chemistry))} батарей</span>
    <span class="mcbi-muted-light">{esc(CATEGORY_MN.get(category, category))}</span>
    <span class="mcbi-id">{esc(battery_id)}</span>
    <img class="mcbi-qr" src="{qr}" alt="QR код · QR code">
  </div>
  <div class="mcbi-passport-body">
    <div class="mcbi-row">
      <span class="mcbi-label">Амьдралын мөчлөг · Lifecycle</span>
      <span class="mcbi-chip">{esc(STATUS_MN.get(status, status))}</span>
    </div>
    {lifecycle_html(status)}
    <span class="mcbi-small">Бүртгэсэн · Registered: {esc(registered)}</span>
    {WASTE_NOTE}
    <p class="mcbi-small">Нийтэд зөвхөн ангилал, химийн төрөл, төлөв
    харагдана. · Only category, chemistry and status are public.</p>
  </div>
</div>
"""


def private_card(values, qr_image):
    qr = image_data_uri(qr_image)
    rows = (
        ("Компани · Company", values["company"]),
        ("Серийн дугаар · Serial", values["serial_number"]),
        ("Загвар · Model", values["model_id"]),
        ("Багц · Batch", values["batch_number"]),
        ("Жин · Weight", f"{fmt_number(values['weight'])} кг"),
        ("Үйлдвэрлэсэн · Made",
         f"{values['country']} · {values['manufacture_date']}"),
        ("Түвшин · Level", LEVEL_MN.get(values["granularity"])),
        ("Бүртгэсэн · Registered", values["registered"]),
    )
    cells = "".join(
        f'<div><dt>{label}</dt><dd>{esc(value)}</dd></div>'
        for label, value in rows
    )
    return f"""
<div class="mcbi-success">
  <span class="mcbi-tick" aria-hidden="true">✓</span>
  <div><strong>Батарей амжилттай бүртгэгдлээ · Registration successful</strong>
  QR кодыг хэвлээд батарейн их бие дээр наана уу.
  · Print the QR code and attach it to the battery.</div>
</div>
<div class="mcbi-passport">
  <div class="mcbi-passport-dark">
    <img class="mcbi-qr" src="{qr}" alt="QR код · QR code">
    <span class="mcbi-eyebrow">БАТАРЕЙН ID</span>
    <span class="mcbi-id">{esc(values['battery_id'])}</span>
  </div>
  <div class="mcbi-passport-body">
    <div class="mcbi-row">
      <span class="mcbi-eyebrow-dark">БАТАРЕЙН ПАСПОРТ · BATTERY PASSPORT</span>
      <span class="mcbi-chip">{esc(STATUS_MN.get(values['status']))}</span>
    </div>
    <span class="mcbi-big-dark">{esc(values['chemistry'])} ·
      {esc(fmt_number(values['capacity']))} {esc(values['capacity_unit'])}</span>
    <span class="mcbi-muted">{esc(CATEGORY_MN.get(values['category']))}</span>
    <dl class="mcbi-grid">{cells}</dl>
    <p class="mcbi-small">Компани, жин, серийн дугаар нууц. QR уншуулсан хүн
    зөвхөн ангилал, химийн төрөл, төлөвийг харна. · Company, weight and
    serial number stay private.</p>
  </div>
</div>
"""


def message_card(text):
    return f'<div class="mcbi-empty">{text}</div>'


LOOKUP_EMPTY = message_card(
    "Батарейн ID-г оруулах эсвэл батарей дээрх QR кодыг утсаараа уншуулна уу."
    "<br><span>Enter a Battery ID or scan the QR code on the battery.</span>"
)


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
    require_admin_key(registration_key, "registration")

    company = required_text(company, "Компани · Company")
    if (
        category not in CATEGORIES
        or chemistry not in CHEMISTRIES
        or granularity not in LEVELS
    ):
        raise gr.Error(
            "Ангилал, химийн төрөл, бүртгэлийн түвшнээ сонгоно уу. · "
            "Select a category, chemistry and registration level."
        )

    if status not in STATUSES or capacity_unit not in CAPACITY_UNITS:
        raise gr.Error(
            "Төлөв болон багтаамжийн нэгжээ сонгоно уу. · "
            "Select a lifecycle status and capacity unit."
        )

    weight = positive_number(weight, "Жин · Weight")
    capacity = positive_number(capacity, "Багтаамж · Capacity")

    country = required_text(country, "Үйлдвэрлэсэн улс · Country")
    manufacture_date = required_text(
        manufacture_date, "Үйлдвэрлэсэн огноо · Manufacturing date"
    )
    model_id = (model_id or "").strip()
    batch_number = (batch_number or "").strip()
    serial_number = (serial_number or "").strip()

    if not re.fullmatch(
        r"\d{4}-(0[1-9]|1[0-2])", manufacture_date
    ):
        raise gr.Error(
            "Огноог ОООО-СС хэлбэрээр бичнэ үү, жишээ нь 2026-09. · "
            "Manufacturing date must use YYYY-MM, for example 2026-09."
        )

    # Drop identification values that this level does not use
    # (e.g. no serial number on an SKU registration).
    level_fields = LEVEL_FIELDS[granularity]
    if "batch_number" not in level_fields:
        batch_number = ""
    if "serial_number" not in level_fields:
        serial_number = ""

    if granularity == "SKU" and not model_id:
        raise gr.Error(
            "Загвараар бүртгэхэд загварын дугаар заавал. · "
            "Model / SKU is required for SKU registrations."
        )

    if granularity == "Batch" and not batch_number:
        raise gr.Error(
            "Багцаар бүртгэхэд багцын дугаар заавал. · "
            "Batch number is required for Batch registrations."
        )

    if granularity == "Unit" and not serial_number:
        raise gr.Error(
            "Ширхэгээр бүртгэхэд серийн дугаар заавал. · "
            "Serial number is required for Unit registrations."
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

    qr = make_qr(battery_id)
    card = private_card({
        "battery_id": battery_id,
        "company": company,
        "category": category,
        "chemistry": chemistry,
        "weight": weight,
        "capacity": capacity,
        "capacity_unit": capacity_unit,
        "granularity": granularity,
        "model_id": model_id,
        "batch_number": batch_number,
        "serial_number": serial_number,
        "country": country,
        "manufacture_date": manufacture_date,
        "status": status,
        "registered": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"),
    }, qr)

    return (
        gr.update(visible=True),
        card,
        battery_id,
        record_link(battery_id),
        gr.update(value=save_qr_file(battery_id, qr)),
    )


def reset_registration_results():
    """Hide the previous result so the next battery starts clean."""
    return gr.update(visible=False), "", "", "", gr.update(value=None)


def find_battery(battery_id):
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return LOOKUP_EMPTY, gr.update(value="", visible=False)

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, category, chemistry, status,
                       registered_at::timestamptz
                FROM batteries
                WHERE id = %s
            """, (battery_id,))
            record = cur.fetchone()

    if record is None:
        return (
            message_card(
                "Энэ ID-тай батарей олдсонгүй. ID-г дахин шалгана уу."
                "<br><span>No battery record found for this ID.</span>"
            ),
            gr.update(value="", visible=False),
        )

    return public_card(record), gr.update(
        value=record_link(record[0]), visible=True
    )


def admin_find_battery(battery_id, admin_key):
    require_admin_key(admin_key)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return "Батарейн ID оруулна уу. · Enter a Battery ID."

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
        return "Батарей олдсонгүй. · No battery record found for this ID."

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
        return "Бүртгэл алга байна. · No batteries registered yet."

    rows = [
        f"Нийт · Total registered: {total}. "
        f"Сүүлийн · Showing the newest {len(records)}:"
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
            "Батарейн ID болон шинэ төлөвөө сонгоно уу. · "
            "Enter a Battery ID and a valid lifecycle status."
        )

    reason = required_text(reason, "Шалтгаан · Reason")

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
                        "Батарей олдсонгүй. · "
                        "No battery record found for this ID."
                    )

                old_status = row[0]

                if old_status == new_status:
                    return (
                        "Төлөв аль хэдийн ийм байна, өөрчлөлт хийгдээгүй. · "
                        "Status is already set to this value."
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

    return f"Төлөв шинэчлэгдлээ · Status updated: {old_status} → {new_status}."


def admin_history(battery_id, admin_key):
    require_admin_key(admin_key)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return "Батарейн ID оруулна уу. · Enter a Battery ID."

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
        return "Түүх алга. · No recorded events for this Battery ID."

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
        raise gr.Error("Батарейн ID оруулна уу. · Enter a Battery ID.")
    if field_label not in EDITABLE_FIELDS:
        raise gr.Error("Засах талбараа сонгоно уу. · Select the field to correct.")

    column = EDITABLE_FIELDS[field_label]
    reason = required_text(reason, "Шалтгаан · Reason")
    new_value = (new_value or "").strip()

    if column in ("company", "country"):
        new_value = required_text(new_value, field_label)
    elif column == "category" and new_value not in CATEGORIES:
        raise gr.Error("Ангилал · Category: " + ", ".join(CATEGORIES))
    elif column == "chemistry" and new_value not in CHEMISTRIES:
        raise gr.Error("Химийн төрөл · Chemistry: " + ", ".join(CHEMISTRIES))
    elif column == "granularity" and new_value not in LEVELS:
        raise gr.Error("Бүртгэлийн түвшин · Level: " + ", ".join(LEVELS))
    elif column == "capacity_unit" and new_value not in CAPACITY_UNITS:
        raise gr.Error("Нэгж · Capacity unit: " + ", ".join(CAPACITY_UNITS))
    elif column in ("weight", "capacity"):
        try:
            number = float(new_value.replace(",", "."))
        except ValueError:
            raise gr.Error(f"{field_label}: тоо оруулна уу. · must be a number.")
        new_value = positive_number(number, field_label)
    elif column == "manufacture_date" and not re.fullmatch(
        r"\d{4}-(0[1-9]|1[0-2])", new_value
    ):
        raise gr.Error(
            "Огноог ОООО-СС хэлбэрээр бичнэ үү, жишээ нь 2026-09. · "
            "Manufacturing date must use YYYY-MM, for example 2026-09."
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
                    raise gr.Error(
                        "Батарей олдсонгүй. · No battery record found for this ID."
                    )
                old_value = row[0]

                if str(old_value) == str(new_value):
                    return (
                        "Өөрчлөлт алга: шинэ утга одоогийнхтой ижил. · "
                        "No change: the new value is the same."
                    )

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

    return f"Засагдлаа · Updated {column}: {old_value} → {new_value}."


def load_battery_from_url(request: gr.Request):
    battery_id = (
        dict(request.query_params).get("battery_id", "")
        if request else ""
    )
    battery_id = battery_id.strip().upper()

    if not battery_id:
        return "", LOOKUP_EMPTY, gr.update(value="", visible=False)

    card, link = find_battery(battery_id)
    return battery_id, card, link


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
        None, None, None, None, "Wh",
        None, "", "", "",
        "", "", "original"
    )


init_database()


# ---------- Look and feel ----------

NAVY = gr.themes.Color(
    c50="#EEF1F8", c100="#E6EAF4", c200="#C4CDE3", c300="#9AA8CC",
    c400="#6F82B2", c500="#2A4079", c600="#0D2253", c700="#0B1D47",
    c800="#0A1A40", c900="#081535", c950="#050D22",
)

THEME = gr.themes.Base(
    primary_hue=NAVY,
    neutral_hue=gr.themes.colors.stone,
    radius_size=gr.themes.sizes.radius_md,
    font=[gr.themes.GoogleFont("IBM Plex Sans"), "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("IBM Plex Mono"), "monospace"],
).set(
    body_background_fill="#F4F2EC",
    body_text_color="#15201F",
    block_background_fill="#FFFFFF",
    block_border_color="#E2DED4",
    block_title_text_color="#15201F",
    block_title_text_weight="600",
    block_title_background_fill="none",
    block_label_background_fill="none",
    block_label_text_color="#55615F",
    input_border_color="#D6D1C4",
    input_border_color_focus="#0D2253",
    button_primary_background_fill="#0D2253",
    button_primary_background_fill_hover="#0A1A40",
    button_primary_text_color="#FFFFFF",
    button_secondary_background_fill="#FFFFFF",
    button_secondary_border_color="#D6D1C4",
    button_secondary_text_color="#15201F",
    button_large_radius="10px",
)

LOGO_URI = "data:image/png;base64,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"

HEADER_HTML = f"""
<header class="mcbi-header">
  <img src="{LOGO_URI}" alt="MCBI лого" width="52" height="52">
  <div class="mcbi-brand">
    <span class="mcbi-title">MCBI EPR</span>
    <span class="mcbi-sub">Монголын тойрог батарейн санаачилга ·
      Battery registration portal</span>
  </div>
  <span class="mcbi-badge">ТУРШИЛТ · PILOT · N-064</span>
</header>
"""

CSS = """
.gradio-container { max-width: 1040px !important; width: 100% !important;
  margin: 0 auto !important; box-sizing: border-box; }
@media (max-width: 640px) {
  .gradio-container .main { width: 100% !important; box-sizing: border-box;
    padding-left: 12px !important; padding-right: 12px !important; }
  .mcbi-card { padding: 14px !important; }
}
.mcbi-header { display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  padding: 8px 0 4px; }
.mcbi-brand { display: flex; flex-direction: column; flex: 1; min-width: 180px; }
.mcbi-title { font-size: 22px; font-weight: 700; letter-spacing: .02em;
  color: #0D2253; }
.mcbi-sub { font-size: 13px; color: #55615F; }
.mcbi-badge { font-size: 12px; font-weight: 600; letter-spacing: .08em;
  color: #8A5300; background: #FBF0DC; padding: 6px 10px; border-radius: 999px; }
.mcbi-intro h2 { margin: 8px 0 4px; font-size: 26px; color: #15201F; }
.mcbi-intro p { margin: 0 0 4px; color: #55615F; }
.mcbi-card { background: #FFFFFF; border: 1px solid #E2DED4 !important;
  border-radius: 14px !important; padding: 22px !important; }
.mcbi-card-active { border: 2px solid #0D2253 !important; }
.mcbi-step-title { display: flex; align-items: center; gap: 10px; margin: 0;
  font-size: 17px; font-weight: 600; color: #15201F; }
.mcbi-step-title span { width: 28px; height: 28px; border-radius: 50%;
  background: #0D2253; color: #FFFFFF; display: inline-flex;
  align-items: center; justify-content: center; font-size: 14px; }
.mcbi-success { display: flex; gap: 14px; align-items: center;
  background: #E6EAF4; border: 1px solid #C4CDE3; border-radius: 14px;
  padding: 16px 20px; margin-bottom: 14px; color: #22325C; }
.mcbi-success strong { display: block; font-size: 17px; color: #0A1A40; }
.mcbi-tick { width: 40px; height: 40px; flex-shrink: 0; border-radius: 50%;
  background: #0D2253; color: #FFFFFF; display: flex; align-items: center;
  justify-content: center; font-size: 20px; font-weight: 700; }
.mcbi-passport { display: flex; flex-wrap: wrap; background: #FFFFFF;
  border: 1px solid #E2DED4; border-radius: 16px; overflow: hidden; }
.mcbi-passport-dark { background: #0D2253; color: #F4F2EC; padding: 24px;
  display: flex; flex-direction: column; gap: 8px; flex: 1 1 260px;
  align-items: flex-start; }
.mcbi-passport-body { padding: 24px; display: flex; flex-direction: column;
  gap: 12px; flex: 2 1 320px; }
.mcbi-qr { width: 190px; height: 190px; background: #FFFFFF; padding: 8px;
  border-radius: 10px; image-rendering: pixelated; }
.mcbi-eyebrow { font-size: 11px; font-weight: 600; letter-spacing: .12em;
  color: #E9B45C; }
.mcbi-eyebrow-dark { font-size: 11px; font-weight: 600; letter-spacing: .12em;
  color: #8A5300; }
.mcbi-big { font-size: 24px; font-weight: 700; line-height: 1.2;
  color: #FFFFFF !important; }
.mcbi-note svg { flex-shrink: 0; width: 26px; height: 30px; }
button.secondary { border: 1px solid #D6D1C4 !important;
  background: #FFFFFF !important; }
button.secondary:hover { background: #F4F2EC !important; }
.mcbi-big-dark { font-size: 24px; font-weight: 700; color: #15201F; }
.mcbi-muted-light { font-size: 14px; color: #C3CBDD; }
.mcbi-muted { font-size: 14px; color: #55615F; }
.mcbi-id { font-family: 'IBM Plex Mono', monospace; font-size: 13px;
  background: #1B3068; color: #FFFFFF; border-radius: 8px; padding: 8px 10px;
  word-break: break-all; }
.mcbi-row { display: flex; justify-content: space-between; align-items: center;
  gap: 12px; flex-wrap: wrap; }
.mcbi-label { font-size: 15px; font-weight: 600; }
.mcbi-chip { font-size: 13px; font-weight: 600; color: #0D2253;
  background: #E6EAF4; padding: 5px 12px; border-radius: 999px; }
.mcbi-grid { margin: 0; display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 14px 20px;
  border-top: 1px solid #E2DED4; padding-top: 16px; }
.mcbi-grid dt { font-size: 12px; color: #55615F; }
.mcbi-grid dd { margin: 2px 0 0; font-size: 14px; font-weight: 500;
  word-break: break-word; }
.mcbi-small { margin: 0; font-size: 12px; line-height: 1.5; color: #55615F; }
.mcbi-life { list-style: none; margin: 0; padding: 0; display: flex;
  flex-direction: column; gap: 10px; }
.mcbi-life li { display: flex; align-items: center; gap: 10px; font-size: 14px;
  color: #55615F; }
.mcbi-life li span { width: 16px; height: 16px; border-radius: 50%;
  border: 2px solid #C9C3B5; box-sizing: border-box; flex-shrink: 0; }
.mcbi-life .mcbi-step-current { color: #15201F; font-weight: 600; }
.mcbi-life .mcbi-step-current span { background: #0D2253; border: 3px solid #C4CDE3; }
.mcbi-life .mcbi-step-done span { background: #9AA8CC; border-color: #9AA8CC; }
.mcbi-note { display: flex; gap: 12px; align-items: flex-start;
  background: #FBF0DC; border: 1px solid #EFD5A6; border-radius: 12px;
  padding: 12px 14px; color: #5E3900; font-size: 13px; line-height: 1.45; }
.mcbi-note strong { display: block; font-size: 14px; }
.mcbi-empty { background: #FFFFFF; border: 1.5px dashed #C9C3B5;
  border-radius: 14px; padding: 28px; text-align: center; color: #15201F; }
.mcbi-empty span { color: #55615F; font-size: 14px; }
#mcbi-footer { opacity: 0.8; font-size: 0.9em; }
"""


with gr.Blocks(title="MCBI EPR Portal") as demo:
    gr.HTML(HEADER_HTML)

    with gr.Tabs():

        # ---------- 1. Public lookup (default tab; QR links open here) ----------
        with gr.Tab("Хайх · Find", id="find"):
            gr.HTML(
                '<div class="mcbi-intro"><h2>Батарей хайх</h2>'
                '<p>Батарейн ID-г оруулах эсвэл QR кодыг уншуулна уу. · '
                'Enter a Battery ID or scan its QR code.</p></div>'
            )
            with gr.Row(equal_height=True):
                lookup_id = gr.Textbox(
                    label="Батарейн ID",
                    info="Battery ID",
                    placeholder="MCBI-8B675499...",
                    scale=4
                )
                lookup_button = gr.Button(
                    "Хайх · Find", variant="primary", scale=1, size="lg"
                )
            lookup_card = gr.HTML(LOOKUP_EMPTY)
            lookup_link = gr.Textbox(
                label="Нийтийн холбоос",
                info="Public link — хуулах товчоор хуваалцана · copy to share",
                interactive=False,
                buttons=["copy"],
                visible=False
            )

            for trigger in (lookup_button.click, lookup_id.submit):
                trigger(
                    fn=find_battery,
                    inputs=lookup_id,
                    outputs=[lookup_card, lookup_link]
                ).then(
                    fn=None,
                    inputs=[lookup_id, lookup_link],
                    js=SYNC_URL_JS
                )

        # ---------- 2. Registration (needs registration key) ----------
        with gr.Tab("Бүртгэх · Register", id="register"):
            gr.HTML(
                '<div class="mcbi-intro"><h2>Батарей бүртгэх</h2>'
                '<p>Бүртгэл бүр өвөрмөц ID, QR код, нийтийн холбоос авна. '
                '«Сонголтоор» гэснээс бусад бүх талбар заавал. · '
                'All fields are required unless marked optional.</p></div>'
            )

            with gr.Column(elem_classes="mcbi-card"):
                gr.HTML('<h3 class="mcbi-step-title"><span>1</span>'
                        'Үндсэн мэдээлэл · Basic information</h3>')
                with gr.Row():
                    company = gr.Textbox(
                        label="Компани / Импортлогч",
                        info="Company / Importer",
                        placeholder="Компанийн нэр"
                    )
                    category = gr.Dropdown(
                        [(f"{CATEGORY_MN[c]}", c) for c in CATEGORIES],
                        value=None,
                        label="Ангилал",
                        info="Category"
                    )
                with gr.Row():
                    chemistry = gr.Dropdown(
                        [(CHEMISTRY_MN.get(c, c), c) for c in CHEMISTRIES],
                        value=None,
                        label="Химийн төрөл",
                        info="Chemistry"
                    )
                    weight = gr.Number(
                        value=None, label="Жин, кг", info="Weight, kg",
                        minimum=0
                    )
                    capacity = gr.Number(
                        value=None, label="Багтаамж", info="Capacity",
                        minimum=0
                    )
                    capacity_unit = gr.Radio(
                        list(CAPACITY_UNITS), value="Wh",
                        label="Нэгж", info="Unit"
                    )

            with gr.Column(elem_classes="mcbi-card"):
                gr.HTML('<h3 class="mcbi-step-title"><span>2</span>'
                        'Таних мэдээлэл · Identification</h3>')
                granularity = gr.Radio(
                    [
                        ("Загвараар · SKU", "SKU"),
                        ("Багцаар · Batch", "Batch"),
                        ("Ширхэгээр · Unit", "Unit"),
                    ],
                    value=None,
                    label="Бүртгэлийн түвшин",
                    info="Registration level"
                )
                level_hint = gr.Markdown(LEVEL_HINTS[None])
                with gr.Row():
                    model_id = gr.Textbox(
                        label=ID_LABELS["model_id"], info=ID_INFO["model_id"],
                        visible=False
                    )
                    batch_number = gr.Textbox(
                        label=ID_LABELS["batch_number"],
                        info=ID_INFO["batch_number"], visible=False
                    )
                    serial_number = gr.Textbox(
                        label=ID_LABELS["serial_number"],
                        info=ID_INFO["serial_number"], visible=False
                    )

                granularity.change(
                    fn=id_field_updates,
                    inputs=granularity,
                    outputs=[model_id, batch_number, serial_number, level_hint]
                )

            with gr.Column(elem_classes="mcbi-card"):
                gr.HTML('<h3 class="mcbi-step-title"><span>3</span>'
                        'Үйлдвэрлэл · Manufacturing</h3>')
                with gr.Row():
                    country = gr.Textbox(
                        label="Үйлдвэрлэсэн улс",
                        info="Country of manufacture",
                        placeholder="ж: Чех, Хятад, Солонгос"
                    )
                    manufacture_date = gr.Textbox(
                        label="Үйлдвэрлэсэн сар",
                        info="Manufacturing month (YYYY-MM)",
                        placeholder="2026-09"
                    )
                    status = gr.Dropdown(
                        [(STATUS_MN[s], s) for s in STATUSES],
                        value="original",
                        label="Амьдралын мөчлөг",
                        info="Lifecycle status"
                    )

            with gr.Column(elem_classes="mcbi-card"):
                gr.HTML('<h3 class="mcbi-step-title"><span>4</span>'
                        'Баталгаажуулах · Confirm</h3>')
                registration_key = gr.Textbox(
                    label="Бүртгэлийн түлхүүр",
                    info="Registration key — MCBI-ээс олгосон түлхүүр",
                    type="password"
                )
                with gr.Row():
                    register_button = gr.Button(
                        "Батарей бүртгэх · Register battery",
                        variant="primary", size="lg", scale=3
                    )
                    clear_button = gr.Button(
                        "Цэвэрлэх · Clear", variant="secondary",
                        size="lg", scale=1
                    )

            with gr.Column(visible=False) as result_group:
                result_card = gr.HTML()
                with gr.Row():
                    battery_id_output = gr.Textbox(
                        label="Батарейн ID", info="Battery ID",
                        interactive=False, buttons=["copy"]
                    )
                    register_link = gr.Textbox(
                        label="Нийтийн холбоос", info="Public link",
                        interactive=False, buttons=["copy"]
                    )
                with gr.Row():
                    qr_download = gr.DownloadButton(
                        "QR шошго татах · Download QR (PNG)",
                        variant="primary", size="lg"
                    )
                    register_another = gr.Button(
                        "Дараагийн батарей бүртгэх · Register another",
                        variant="secondary", size="lg"
                    )

            battery_fields = [
                category, chemistry, weight, capacity, capacity_unit,
                granularity, model_id, batch_number, serial_number,
                country, manufacture_date, status
            ]
            result_outputs = [
                result_group, result_card, battery_id_output, register_link,
                qr_download
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

            clear_button.click(
                fn=clear_battery_fields,
                inputs=[],
                outputs=battery_fields
            )

        # ---------- 3. Admin ----------
        with gr.Tab("Админ · Admin", id="admin"):
            gr.HTML(
                '<div class="mcbi-intro"><h2>Админ</h2>'
                '<p>Түлхүүрээ бусадтай хуваалцах, нийтийн компьютер дээр '
                'үлдээхгүй байгаарай. · Do not share your key or leave it '
                'on a shared computer.</p></div>'
            )
            with gr.Column(elem_classes="mcbi-card"):
                admin_key = gr.Textbox(
                    label="Админ түлхүүр", info="Admin key",
                    type="password"
                )

                recent_records = gr.Textbox(
                    label="Сүүлийн бүртгэлүүд",
                    info="Recent registrations",
                    lines=10,
                    interactive=False
                )
                gr.Button("Бүртгэлүүдийг харах · Show registrations").click(
                    fn=admin_list_batteries,
                    inputs=admin_key,
                    outputs=recent_records
                )

            with gr.Column(elem_classes="mcbi-card"):
                admin_id = gr.Textbox(label="Батарейн ID", info="Battery ID")

                with gr.Row():
                    view_button = gr.Button("Дэлгэрэнгүй · Private record")
                    history_button = gr.Button("Түүх · History")
                admin_result = gr.Textbox(
                    label="Нууц мэдээлэл", info="Private record",
                    lines=14,
                    interactive=False
                )
                history_result = gr.Textbox(
                    label="Бүртгэл ба төлөвийн түүх", info="History",
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

            with gr.Column(elem_classes="mcbi-card"):
                gr.HTML('<h3 class="mcbi-step-title">'
                        'Төлөв өөрчлөх · Change status</h3>')
                with gr.Row():
                    new_status = gr.Dropdown(
                        [(f"{STATUS_MN[s]} · {s}", s) for s in STATUSES],
                        label="Шинэ төлөв", info="New status"
                    )
                    status_reason = gr.Textbox(
                        label="Шалтгаан", info="Reason"
                    )
                status_result = gr.Textbox(
                    label="Үр дүн", info="Result",
                    interactive=False
                )
                gr.Button("Төлөв шинэчлэх · Update status").click(
                    fn=change_status,
                    inputs=[admin_id, new_status, status_reason, admin_key],
                    outputs=status_result
                )

            with gr.Column(elem_classes="mcbi-card"):
                gr.HTML('<h3 class="mcbi-step-title">'
                        'Бүртгэл засах · Correct a record</h3>'
                        '<p class="mcbi-small">Алдаатай бичсэн талбарыг засна. '
                        'Хуучин утга түүхэнд хадгалагдана. · Fix a mistyped '
                        'field; the old value is kept in the history.</p>')
                with gr.Row():
                    edit_field = gr.Dropdown(
                        list(EDITABLE_FIELDS),
                        label="Засах талбар", info="Field"
                    )
                    edit_value = gr.Textbox(
                        label="Зөв утга", info="Correct value"
                    )
                edit_reason = gr.Textbox(
                    label="Шалтгаан", info="Reason",
                    placeholder="Жишээ нь: Багтаамжийг буруу бичсэн"
                )
                edit_result = gr.Textbox(
                    label="Үр дүн", info="Result",
                    interactive=False
                )
                gr.Button("Засвар хадгалах · Save correction").click(
                    fn=edit_battery,
                    inputs=[admin_id, edit_field, edit_value, edit_reason,
                            admin_key],
                    outputs=edit_result
                )

    gr.Markdown(
        """
        ---
        **MCBI EPR Pilot — N-064** · Монголын тойрог батарейн санаачилга ·
        Туршилтын хувилбар · Pilot prototype
        """,
        elem_id="mcbi-footer"
    )

    demo.load(
        fn=load_battery_from_url,
        inputs=[],
        outputs=[lookup_id, lookup_card, lookup_link]
    )
    demo.load(fn=lambda: (None, None), inputs=[], outputs=[weight, capacity])


port = int(os.getenv("PORT", "10000"))

demo.launch(
    server_name="0.0.0.0",
    server_port=port,
    ssr_mode=False,
    pwa=True,
    css=CSS,
    theme=THEME
)
