import gradio as gr
import uuid
from datetime import datetime
import os
import hmac
import psycopg2
import qrcode

DATABASE_URL = os.getenv("DATABASE_URL")


def make_qr(battery_id):
    """Encode the battery ID as a QR image for a pilot label."""
    return qrcode.make(battery_id).convert("RGB")


def init_database():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
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
    conn.commit()
    cur.close()
    conn.close()


init_database()


def register_battery(
    company,
    category,
    chemistry,
    weight,
    capacity,
    granularity,
    model_id,
    batch_number,
    serial_number,
    country,
    manufacture_date,
    status,
    registration_key
):
    expected_key = os.getenv("REGISTRATION_KEY")
    if not expected_key or not hmac.compare_digest(registration_key or "", expected_key):
        raise gr.Error("Registration key is missing or incorrect.")

    battery_id = "MCBI-" + str(uuid.uuid4())[:8].upper()
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO batteries (
            id, company, category, chemistry, weight, capacity,
            granularity, model_id, batch_number, serial_number,
            country, manufacture_date, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        battery_id, company, category, chemistry, weight, capacity,
        granularity, model_id, batch_number, serial_number,
        country, manufacture_date, status
    ))
    conn.commit()
    cur.close()
    conn.close()

    result = f"""
# MCBI Battery Record
**Battery ID:** {battery_id}
**Company / Importer:** {company}
**Category:** {category}
**Chemistry:** {chemistry}
**Weight:** {weight} kg
**Capacity:** {capacity} Wh/Ah
**Registration level:** {granularity}
**Model / SKU:** {model_id}
**Batch number:** {batch_number}
**Serial number:** {serial_number}
**Manufacturing country:** {country}
**Manufacturing date:** {manufacture_date}
**Lifecycle status:** {status}
**Registered:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
---
MCBI EPR Pilot Portal
Pilot / demonstration record
"""
    return battery_id, result, make_qr(battery_id)


def find_battery(battery_id):
    battery_id = (battery_id or "").strip().upper()
    if not battery_id:
        return "Please enter a Battery ID.", None

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, company, category, chemistry, weight, capacity,
                       granularity, model_id, batch_number, serial_number,
                       country, manufacture_date, status, registered_at
                FROM batteries WHERE id = %s
            """, (battery_id,))
            record = cur.fetchone()

    if record is None:
        return "No battery record found for this ID.", None

    labels = (
        "Battery ID", "Company / Importer", "Category", "Chemistry",
        "Weight (kg)", "Capacity (Wh/Ah)", "Registration level",
        "Model / SKU", "Batch number", "Serial number",
        "Manufacturing country", "Manufacturing date", "Lifecycle status",
        "Registered"
    )
    details = "\n".join(
        f"{label}: {value if value is not None else '—'}"
        for label, value in zip(labels, record)
    )
    return details, make_qr(record[0])


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
            ["EV", "LMT", "Stationary", "Industrial", "Consumer"],
            label="Battery Category"
        )

    with gr.Row():
        chemistry = gr.Dropdown(
            ["LFP", "NMC", "NCA", "LCO", "LMO", "Lead-acid", "Other"],
            label="Chemistry"
        )
        granularity = gr.Dropdown(
            ["SKU", "Batch", "Unit"],
            label="Registration Level"
        )

    with gr.Row():
        weight = gr.Number(label="Weight (kg)")
        capacity = gr.Number(label="Capacity (Wh/Ah)")

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
        ["original", "repurposed", "re-used", "remanufactured", "waste"],
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
    record_output = gr.Markdown()
    gr.Markdown("The QR code contains the Battery ID for pilot labels.")
    qr_output = gr.Image(
        label="Battery ID QR Code",
        type="pil",
        interactive=False
    )

    register_button.click(
        fn=register_battery,
        inputs=[
            company, category, chemistry, weight, capacity,
            granularity, model_id, batch_number, serial_number,
            country, manufacture_date, status, registration_key
        ],
        outputs=[battery_id_output, record_output, qr_output]
    )

    gr.Markdown("### Find a Registered Battery")
    lookup_id = gr.Textbox(
        label="Battery ID",
        placeholder="MCBI-8B675499"
    )
    lookup_button = gr.Button("Find Battery")
    lookup_result = gr.Textbox(
        label="Stored Battery Record",
        lines=15,
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

    gr.Markdown("""
    ---
    **MCBI EPR Pilot — N-064**
    Prototype for testing battery identification and EPR data flows.
    """)

demo.launch(server_name="0.0.0.0", server_port=10000, ssr_mode=False)
