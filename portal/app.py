import base64
import csv
import hmac
import html
import io
import json
import math
import hashlib
import secrets
import os
import re
import tempfile
import time
import uuid
import zipfile
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote

import gradio as gr
import psycopg2
import qrcode
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse


DATABASE_URL = os.getenv("DATABASE_URL")
# Public address of the portal. Every QR code points to PORTAL_URL/b/<ID>.
# Set it to your own domain (for example https://passport.mcbis.org) and keep
# that domain for good: printed QR labels live as long as the batteries do.
PORTAL_URL = os.getenv(
    "PORTAL_URL",
    "https://mcbi-epr-system.onrender.com"
).rstrip("/")

CATEGORIES = ("SLI", "EV", "LMT", "Stationary", "Industrial", "Consumer")
CHEMISTRIES = ("LFP", "NMC", "NCA", "LCO", "LMO", "Lead-acid", "Other")
LEVELS = ("SKU", "Batch", "Unit")
CAPACITY_UNITS = ("Wh", "Ah")
STATUSES = ("original", "repurposed", "re-used", "remanufactured", "waste")
ORG_KINDS = ("manufacturer", "importer", "recycler", "repurposer", "other")
# Organization types treated as "persons with a legitimate interest"
INTEREST_KINDS = ("recycler", "repurposer")
MAX_CSV_ROWS = 500
MAX_CSV_BYTES = 2_000_000

LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TIMEZONE", "Asia/Ulaanbaatar"))

# ======================================================================
# LANGUAGES
# Every piece of text the user sees lives in TEXT below, one language at a
# time. To add a language (for example Czech), add its code to LANGUAGES
# and copy the "en" block under a new key, then translate the values.
# The database always stores the English codes (LFP, original, SKU ...).
# ======================================================================

LANGUAGES = (("Монгол", "mn"), ("English", "en"))
DEFAULT_LANG = "en"   # used when the browser does not ask for Mongolian

TEXT = {
    "en": {
        # header and tabs
        "brand_sub": "Mongolia Circular Battery Initiative · Battery registration portal",
        "badge": "PILOT · N-064",
        "tab_find": "Find",
        "tab_register": "Register",
        "tab_epr": "EPR report",
        "tab_org": "Organization signup",
        "tab_admin": "Admin",
        "footer": "Mongolia Circular Battery Initiative · Pilot prototype",

        # account bar (sign in once)
        "signin_hint": "Sign in with your approved organization account to register batteries and file EPR reports.",
        "acct_email": "Organization email",
        "acct_password": "Password",
        "btn_signin": "Sign in",
        "btn_signout": "Sign out",
        "signed_in_as": "Signed in as **{name}** · {kind}",
        "err_sign_in": "Please sign in first (top of the page).",

        # find tab
        "find_title": "Find a battery",
        "find_intro": "Enter a Battery ID or scan its QR code.",
        "battery_id": "Battery ID",
        "btn_find": "Find",
        "public_link": "Public link",
        "public_link_info": "Copy it to share this record",
        "lookup_empty": "Enter a Battery ID or scan the QR code on the battery.",
        "lookup_notfound": "No battery record found for this ID. Please check the ID.",

        # public passport card
        "pp_eyebrow": "BATTERY PASSPORT",
        "battery_word": "battery",
        "lifecycle": "Lifecycle",
        "registered": "Registered",
        "public_note": "Public: category, chemistry, status, energy, carbon footprint and recycled content. Company, weight and serial number need access.",
        "qr_alt": "QR code",
        "life_1": "New · in use",
        "life_2": "Reuse / second life",
        "life_3": "Collection and recycling",
        "waste_title": "Do not dispose of with household waste",
        "waste_text": "Take used batteries to a collection point.",
        "energy_word": "Energy",
        "passport_word": "Battery passport",
        "passport_yes": "Required (EU, from 18 February 2027)",
        "passport_no": "Not required",
        "passport_unknown": "Depends on capacity (required above 2 kWh)",
        "carbon_word": "Carbon footprint",
        "recycled_word": "Recycled content",
        "json_word": "Machine-readable record (JSON)",

        # private card (after registering)
        "success_title": "Battery registered successfully",
        "success_text": "Print the QR code and attach it to the battery.",
        "battery_id_caps": "BATTERY ID",
        "company": "Company",
        "serial": "Serial number",
        "model": "Model",
        "batch": "Batch",
        "weight_word": "Weight",
        "voltage_word": "Voltage",
        "kg": "kg",
        "made": "Made",
        "level": "Level",
        "private_note": "Company, weight and serial number need access. Anyone who scans the QR code sees the public details only.",

        # organization signup
        "org_title": "Organization signup",
        "org_intro": "Register your organization below. Battery registration becomes available after an MCBI administrator approves it.",
        "org_name": "Organization name",
        "org_email": "Organization email",
        "org_password_new": "Password (12+ characters)",
        "org_kind": "Organization type",
        "org_country": "Country",
        "result": "Result",
        "btn_org_submit": "Submit organization request",

        # register tab
        "reg_title": "Register a battery",
        "reg_intro": "Every record gets a unique ID, a QR code and a public link. All fields are required unless marked optional.",
        "step1": "Basic information",
        "step2": "Identification",
        "step3": "Manufacturing",
        "step4": "Confirm",
        "company_note": "The company is taken from the organization you are signed in with.",
        "category": "Category",
        "chemistry": "Chemistry",
        "weight_kg": "Weight, kg",
        "capacity": "Capacity",
        "unit": "Unit",
        "voltage": "Nominal voltage, V",
        "voltage_info": "Needed when capacity is in Ah",
        "reg_level": "Registration level",
        "level_hint_none": "Select a registration level first; the identification fields depend on it.",
        "level_hint_SKU": "**Model / SKU** — registers a whole model. A model identifier is required.",
        "level_hint_Batch": "**Batch** — registers one production batch. Batch number is required; model is optional.",
        "level_hint_Unit": "**Individual unit** — registers a single battery. Serial number is required; model and batch are optional.",
        "id_model": "Model / SKU",
        "id_batch": "Batch number",
        "id_serial": "Serial number",
        "optional_suffix": " (optional)",
        "country": "Country of manufacture",
        "country_ph": "e.g. Czech Republic, China, South Korea",
        "mfg_date": "Manufacturing month",
        "mfg_date_info": "Format YYYY-MM",
        "lifecycle_status": "Lifecycle status",
        "passport_acc": "Passport details (optional)",
        "carbon": "Carbon footprint, kg CO₂e per kWh",
        "recycled": "Recycled content, %",
        "soh": "State of health, %",
        "mfr_address": "Manufacturer address",
        "btn_register": "Register battery",
        "btn_clear": "Clear",
        "btn_download_qr": "Download QR label (PNG)",
        "btn_register_another": "Register another battery",

        # bulk (csv)
        "bulk_title": "Register many batteries (CSV)",
        "bulk_intro": "Download the template, replace the example row with one battery per row (up to {max} rows) and upload it. All rows are checked first; nothing is saved unless every row is valid. You get a ZIP with the new IDs and one QR image per battery.",
        "btn_template": "Download CSV template",
        "bulk_file": "CSV file",
        "btn_bulk": "Register all from CSV",
        "bulk_result": "Result",
        "bulk_zip": "Results and QR labels (ZIP)",
        "btn_export_mine": "Download my batteries (CSV)",
        "file_word": "File",
        "err_no_file": "Choose a CSV file first.",
        "err_csv_read": "Could not read the file. Save it as CSV (UTF-8).",
        "err_csv_empty": "The file has no data rows.",
        "err_csv_cols": "Missing columns: {cols}.",
        "err_csv_too_many": "Too many rows ({n}). The maximum is {max}.",
        "msg_csv_errors": "Nothing was saved. Fix these rows and upload again:",
        "msg_csv_row": "Row {n}: {msg}",
        "msg_csv_done": "Registered {n} batteries. Download the ZIP below.",

        # EPR report tab
        "epr_title": "EPR report: batteries placed on the market",
        "epr_intro": "Report how many batteries your organization placed on the market each year. Saving again for the same year and category replaces the earlier figure.",
        "epr_year": "Year",
        "epr_units": "Units placed on the market",
        "epr_weight": "Total weight, kg",
        "btn_save_report": "Save report",
        "btn_show_reports": "Show my reports",
        "msg_report_saved": "Saved: {year} · {category}: {units} units, {weight} kg.",
        "msg_no_reports": "No reports yet.",
        "th_year": "Year",
        "th_category": "Category",
        "th_units": "Units",
        "th_weight": "Weight, kg",
        "th_orgs": "Organizations",
        "th_total": "Total",
        "err_year": "Year must be between 2020 and 2100.",
        "err_int": "{label} must be a whole number, zero or more.",

        # admin tab
        "admin_title": "Administration",
        "admin_intro": "Do not share your key or leave it on a shared computer.",
        "admin_key": "Admin key",
        "recent_regs": "Recent registrations",
        "btn_show_regs": "Show registrations",
        "btn_export_all": "Export all batteries (CSV)",
        "btn_market": "Market summary (EPR)",
        "market_summary": "Market summary",
        "org_section": "### Approve organization requests",
        "organizations": "Organizations",
        "btn_show_orgs": "Show organizations",
        "approve_id": "Organization ID to approve",
        "approve_result": "Approval result",
        "btn_approve": "Approve organization",
        "btn_private": "Full record",
        "btn_history": "History",
        "private_record": "Full record",
        "history": "Registration and status history",
        "status_title": "Change status",
        "new_status": "New status",
        "reason": "Reason",
        "btn_update_status": "Update status",
        "edit_title": "Correct a record",
        "edit_note": "Fix a mistyped field. The old value is kept in the history. Leave the value empty to clear an optional field.",
        "edit_field": "Field to correct",
        "edit_value": "Correct value",
        "edit_reason_ph": "e.g. Correcting a mistyped capacity",
        "btn_save_edit": "Save correction",

        # messages
        "err_too_many": "Too many failed attempts. Try again in 15 minutes.",
        "err_admin_key": "Admin key is missing or incorrect.",
        "err_email": "Please enter a valid email address.",
        "err_password_short": "Password must contain at least 12 characters.",
        "err_org_exists": "An organization with this email is already registered.",
        "msg_org_submitted": "Request submitted. You can register batteries after approval by an MCBI administrator.",
        "err_login": "Incorrect organization email or password.",
        "err_not_approved": "Your organization is awaiting administrator approval.",
        "err_select_kind": "Select the organization type.",
        "msg_no_orgs": "No organizations found.",
        "org_approved_word": "Approved",
        "org_pending_word": "Pending",
        "err_org_id": "Organization ID must be a number.",
        "err_org_missing": "Organization not found.",
        "msg_org_approved": "{name} has been approved.",
        "err_required": "{label} is required.",
        "err_positive": "{label} must be a positive number.",
        "err_range": "{label} must be between {lo} and {hi}.",
        "err_too_long": "{label} is too long (at most {n} characters).",
        "err_select_main": "Select a category, chemistry and registration level.",
        "err_select_status": "Select a lifecycle status and capacity unit.",
        "err_voltage_required": "Nominal voltage is required when capacity is in Ah.",
        "err_date": "Manufacturing date must use YYYY-MM, for example 2026-09.",
        "err_need_model": "Model / SKU is required for SKU registrations.",
        "err_need_batch": "Batch number is required for Batch registrations.",
        "err_need_serial": "Serial number is required for Unit registrations.",
        "err_enter_id": "Enter a Battery ID.",
        "err_battery_missing": "No battery record found for this ID.",
        "msg_no_batteries": "No batteries registered yet.",
        "list_header": "Total registered: {total}. Showing the newest {n}:",
        "err_status_inputs": "Enter a Battery ID and a valid lifecycle status.",
        "msg_status_same": "Status is already set to this value. Nothing changed.",
        "msg_status_updated": "Status updated: {old} → {new}.",
        "msg_no_history": "No recorded events for this Battery ID.",
        "err_select_field": "Select the field to correct.",
        "err_allowed": "{field}: allowed values are {values}.",
        "err_number": "{field} must be a number.",
        "msg_no_change": "No change: the new value is the same as the current one.",
        "msg_edited": "Updated {column}: {old} → {new}.",
        "ev_registered": "registered",
        "ev_status_changed": "status changed",
        "ev_edited": "edited",
    },
    "mn": {
        "brand_sub": "Монголын тойрог батарейн санаачилга · Батарей бүртгэлийн портал",
        "badge": "ТУРШИЛТ · N-064",
        "tab_find": "Хайх",
        "tab_register": "Бүртгэх",
        "tab_epr": "EPR тайлан",
        "tab_org": "Байгууллага бүртгүүлэх",
        "tab_admin": "Админ",
        "footer": "Монголын тойрог батарейн санаачилга · Туршилтын хувилбар",

        "signin_hint": "Батарей бүртгэх, EPR тайлан өгөхийн тулд зөвшөөрөгдсөн байгууллагынхаа бүртгэлээр нэвтэрнэ үү.",
        "acct_email": "Байгууллагын имэйл",
        "acct_password": "Нууц үг",
        "btn_signin": "Нэвтрэх",
        "btn_signout": "Гарах",
        "signed_in_as": "Нэвтэрсэн: **{name}** · {kind}",
        "err_sign_in": "Эхлээд нэвтэрнэ үү (хуудасны дээд хэсэгт).",

        "find_title": "Батарей хайх",
        "find_intro": "Батарейн ID-г оруулах эсвэл QR кодыг уншуулна уу.",
        "battery_id": "Батарейн ID",
        "btn_find": "Хайх",
        "public_link": "Нийтийн холбоос",
        "public_link_info": "Хуулж аваад бүртгэлийг хуваалцана уу",
        "lookup_empty": "Батарейн ID-г оруулах эсвэл батарей дээрх QR кодыг утсаараа уншуулна уу.",
        "lookup_notfound": "Энэ ID-тай батарей олдсонгүй. ID-г дахин шалгана уу.",

        "pp_eyebrow": "БАТАРЕЙН ПАСПОРТ",
        "battery_word": "батарей",
        "lifecycle": "Амьдралын мөчлөг",
        "registered": "Бүртгэсэн",
        "public_note": "Нийтэд харагдах: ангилал, химийн төрөл, төлөв, энерги, нүүрстөрөгчийн ул мөр, дахин боловсруулсан материалын хувь. Компани, жин, серийн дугаарыг эрхтэй хүн л харна.",
        "qr_alt": "QR код",
        "life_1": "Шинэ · ашиглалтад",
        "life_2": "Дахин ашиглалт / хоёр дахь амьдрал",
        "life_3": "Цуглуулалт ба дахин боловсруулалт",
        "waste_title": "Энгийн хогтой хамт хаяж болохгүй",
        "waste_text": "Ашиглалтаас гарсан батарейг цуглуулах цэгт хүлээлгэн өгнө.",
        "energy_word": "Энерги",
        "passport_word": "Батарейн паспорт",
        "passport_yes": "Шаардлагатай (ЕХ, 2027 оны 2-р сарын 18-наас)",
        "passport_no": "Шаардлагагүй",
        "passport_unknown": "Багтаамжаас хамаарна (2 кВт·цагаас дээш бол шаардлагатай)",
        "carbon_word": "Нүүрстөрөгчийн ул мөр",
        "recycled_word": "Дахин боловсруулсан материал",
        "json_word": "Машин уншихуйц бүртгэл (JSON)",

        "success_title": "Батарей амжилттай бүртгэгдлээ",
        "success_text": "QR кодыг хэвлээд батарейн их бие дээр наана уу.",
        "battery_id_caps": "БАТАРЕЙН ID",
        "company": "Компани",
        "serial": "Серийн дугаар",
        "model": "Загвар",
        "batch": "Багц",
        "weight_word": "Жин",
        "voltage_word": "Хүчдэл",
        "kg": "кг",
        "made": "Үйлдвэрлэсэн",
        "level": "Түвшин",
        "private_note": "Компани, жин, серийн дугаарыг эрхтэй хүн л харна. QR уншуулсан хүн зөвхөн нийтийн мэдээллийг харна.",

        "org_title": "Байгууллагын бүртгэл",
        "org_intro": "Байгууллагаа доор бүртгүүлнэ үү. MCBI админ зөвшөөрсний дараа батарей бүртгэх боломжтой болно.",
        "org_name": "Байгууллагын нэр",
        "org_email": "Байгууллагын имэйл",
        "org_password_new": "Нууц үг (12+ тэмдэгт)",
        "org_kind": "Байгууллагын төрөл",
        "org_country": "Улс",
        "result": "Үр дүн",
        "btn_org_submit": "Байгууллага бүртгүүлэх",

        "reg_title": "Батарей бүртгэх",
        "reg_intro": "Бүртгэл бүр өвөрмөц ID, QR код, нийтийн холбоос авна. «Сонголтоор» гэснээс бусад бүх талбар заавал.",
        "step1": "Үндсэн мэдээлэл",
        "step2": "Таних мэдээлэл",
        "step3": "Үйлдвэрлэл",
        "step4": "Баталгаажуулах",
        "company_note": "Компани нь таны нэвтэрсэн байгууллагын нэрээр автоматаар бүртгэгдэнэ.",
        "category": "Ангилал",
        "chemistry": "Химийн төрөл",
        "weight_kg": "Жин, кг",
        "capacity": "Багтаамж",
        "unit": "Нэгж",
        "voltage": "Нэрлэсэн хүчдэл, В",
        "voltage_info": "Багтаамж Ah-аар бол заавал",
        "reg_level": "Бүртгэлийн түвшин",
        "level_hint_none": "Эхлээд бүртгэлийн түвшнээ сонгоно уу. Доорх талбарууд түүнээс хамаарна.",
        "level_hint_SKU": "**Загвараар** — нэг загварыг бүхэлд нь бүртгэнэ. Загварын дугаар заавал.",
        "level_hint_Batch": "**Багцаар** — нэг үйлдвэрлэлийн багцыг бүртгэнэ. Багцын дугаар заавал, загвар нь сонголтоор.",
        "level_hint_Unit": "**Ширхэгээр** — нэг ширхэг батарейг бүртгэнэ. Серийн дугаар заавал, загвар ба багц сонголтоор.",
        "id_model": "Загвар / SKU",
        "id_batch": "Багцын дугаар",
        "id_serial": "Серийн дугаар",
        "optional_suffix": " (сонголтоор)",
        "country": "Үйлдвэрлэсэн улс",
        "country_ph": "ж: Чех, Хятад, Өмнөд Солонгос",
        "mfg_date": "Үйлдвэрлэсэн сар",
        "mfg_date_info": "ОООО-СС хэлбэрээр",
        "lifecycle_status": "Амьдралын мөчлөг",
        "passport_acc": "Паспортын мэдээлэл (сонголтоор)",
        "carbon": "Нүүрстөрөгчийн ул мөр, кг CO₂e/кВт·цаг",
        "recycled": "Дахин боловсруулсан материал, %",
        "soh": "Эрүүл мэндийн төлөв (SoH), %",
        "mfr_address": "Үйлдвэрлэгчийн хаяг",
        "btn_register": "Батарей бүртгэх",
        "btn_clear": "Цэвэрлэх",
        "btn_download_qr": "QR шошго татах (PNG)",
        "btn_register_another": "Дараагийн батарей бүртгэх",

        "bulk_title": "Олон батарей нэг дор бүртгэх (CSV)",
        "bulk_intro": "Загвар файлыг татаж, жишээ мөрийг солиод нэг мөрөнд нэг батарей бичнэ (хамгийн ихдээ {max} мөр). Дараа нь файлаа оруулна. Бүх мөрийг эхлээд шалгана, нэг мөр алдаатай бол юу ч хадгалагдахгүй. Шинэ ID-нууд болон батарей бүрийн QR зурагтай ZIP файл авна.",
        "btn_template": "CSV загвар татах",
        "bulk_file": "CSV файл",
        "btn_bulk": "CSV-ээс бүгдийг бүртгэх",
        "bulk_result": "Үр дүн",
        "bulk_zip": "Үр дүн ба QR шошгууд (ZIP)",
        "btn_export_mine": "Миний батарейнууд (CSV татах)",
        "file_word": "Файл",
        "err_no_file": "Эхлээд CSV файлаа сонгоно уу.",
        "err_csv_read": "Файлыг уншиж чадсангүй. CSV (UTF-8) хэлбэрээр хадгална уу.",
        "err_csv_empty": "Файлд өгөгдлийн мөр алга.",
        "err_csv_cols": "Дутуу багана: {cols}.",
        "err_csv_too_many": "Мөр хэт их байна ({n}). Дээд хязгаар {max}.",
        "msg_csv_errors": "Юу ч хадгалагдсангүй. Дараах мөрүүдийг засаад дахин оруулна уу:",
        "msg_csv_row": "{n}-р мөр: {msg}",
        "msg_csv_done": "{n} батарей бүртгэгдлээ. Доорх ZIP файлыг татаж аваарай.",

        "epr_title": "EPR тайлан: зах зээлд нийлүүлсэн батарей",
        "epr_intro": "Байгууллага жил бүр зах зээлд хэдэн батарей нийлүүлснээ тайлагнана. Нэг жил, нэг ангилалд дахин хадгалбал өмнөх тоог солино.",
        "epr_year": "Он",
        "epr_units": "Зах зээлд нийлүүлсэн ширхэг",
        "epr_weight": "Нийт жин, кг",
        "btn_save_report": "Тайлан хадгалах",
        "btn_show_reports": "Миний тайлангууд",
        "msg_report_saved": "Хадгалагдлаа: {year} · {category}: {units} ширхэг, {weight} кг.",
        "msg_no_reports": "Тайлан алга.",
        "th_year": "Он",
        "th_category": "Ангилал",
        "th_units": "Ширхэг",
        "th_weight": "Жин, кг",
        "th_orgs": "Байгууллага",
        "th_total": "Нийт",
        "err_year": "Он 2020-оос 2100 хооронд байна.",
        "err_int": "{label}: 0 ба түүнээс их бүхэл тоо оруулна уу.",

        "admin_title": "Админ",
        "admin_intro": "Түлхүүрээ бусадтай хуваалцах, нийтийн компьютер дээр үлдээхгүй байгаарай.",
        "admin_key": "Админ түлхүүр",
        "recent_regs": "Сүүлийн бүртгэлүүд",
        "btn_show_regs": "Бүртгэлүүдийг харах",
        "btn_export_all": "Бүх батарейг CSV-ээр татах",
        "btn_market": "Зах зээлийн нэгтгэл (EPR)",
        "market_summary": "Зах зээлийн нэгтгэл",
        "org_section": "### Байгууллагын хүсэлт зөвшөөрөх",
        "organizations": "Байгууллагууд",
        "btn_show_orgs": "Байгууллагуудыг харах",
        "approve_id": "Зөвшөөрөх байгууллагын ID",
        "approve_result": "Зөвшөөрлийн үр дүн",
        "btn_approve": "Байгууллага зөвшөөрөх",
        "btn_private": "Бүрэн мэдээлэл",
        "btn_history": "Түүх",
        "private_record": "Бүрэн мэдээлэл",
        "history": "Бүртгэл ба төлөвийн түүх",
        "status_title": "Төлөв өөрчлөх",
        "new_status": "Шинэ төлөв",
        "reason": "Шалтгаан",
        "btn_update_status": "Төлөв шинэчлэх",
        "edit_title": "Бүртгэл засах",
        "edit_note": "Алдаатай бичсэн талбарыг засна. Хуучин утга түүхэнд хадгалагдана. Сонголтоор бөглөдөг талбарыг арилгахын тулд утгыг хоосон үлдээнэ.",
        "edit_field": "Засах талбар",
        "edit_value": "Зөв утга",
        "edit_reason_ph": "Жишээ нь: Багтаамжийг буруу бичсэн",
        "btn_save_edit": "Засвар хадгалах",

        "err_too_many": "Хэт олон буруу оролдлого. 15 минутын дараа дахин оролдоно уу.",
        "err_admin_key": "Админ түлхүүр хоосон эсвэл буруу байна.",
        "err_email": "Имэйл хаягаа шалгана уу.",
        "err_password_short": "Нууц үг хамгийн багадаа 12 тэмдэгттэй байна.",
        "err_org_exists": "Энэ имэйлээр байгууллага бүртгэлтэй байна.",
        "msg_org_submitted": "Хүсэлт илгээгдлээ. MCBI админ зөвшөөрсний дараа батарей бүртгэх боломжтой.",
        "err_login": "Байгууллагын имэйл эсвэл нууц үг буруу.",
        "err_not_approved": "Байгууллагын бүртгэлийг админ хараахан зөвшөөрөөгүй байна.",
        "err_select_kind": "Байгууллагын төрлөө сонгоно уу.",
        "msg_no_orgs": "Байгууллага алга.",
        "org_approved_word": "Зөвшөөрсөн",
        "org_pending_word": "Хүлээгдэж буй",
        "err_org_id": "Байгууллагын ID тоо байх ёстой.",
        "err_org_missing": "Байгууллага олдсонгүй.",
        "msg_org_approved": "{name} байгууллагыг зөвшөөрлөө.",
        "err_required": "{label}: заавал бөглөнө.",
        "err_positive": "{label}: 0-ээс их тоо оруулна уу.",
        "err_range": "{label}: {lo}-оос {hi} хооронд байна.",
        "err_too_long": "{label} хэт урт байна (хамгийн ихдээ {n} тэмдэгт).",
        "err_select_main": "Ангилал, химийн төрөл, бүртгэлийн түвшнээ сонгоно уу.",
        "err_select_status": "Төлөв болон багтаамжийн нэгжээ сонгоно уу.",
        "err_voltage_required": "Багтаамж Ah-аар бол нэрлэсэн хүчдэл заавал.",
        "err_date": "Огноог ОООО-СС хэлбэрээр бичнэ үү, жишээ нь 2026-09.",
        "err_need_model": "Загвараар бүртгэхэд загварын дугаар заавал.",
        "err_need_batch": "Багцаар бүртгэхэд багцын дугаар заавал.",
        "err_need_serial": "Ширхэгээр бүртгэхэд серийн дугаар заавал.",
        "err_enter_id": "Батарейн ID оруулна уу.",
        "err_battery_missing": "Энэ ID-тай батарей олдсонгүй.",
        "msg_no_batteries": "Бүртгэл алга байна.",
        "list_header": "Нийт бүртгэсэн: {total}. Сүүлийн {n}:",
        "err_status_inputs": "Батарейн ID болон шинэ төлөвөө сонгоно уу.",
        "msg_status_same": "Төлөв аль хэдийн ийм байна, өөрчлөлт хийгдээгүй.",
        "msg_status_updated": "Төлөв шинэчлэгдлээ: {old} → {new}.",
        "msg_no_history": "Энэ ID-д түүх алга.",
        "err_select_field": "Засах талбараа сонгоно уу.",
        "err_allowed": "{field}: зөвшөөрөгдсөн утгууд: {values}.",
        "err_number": "{field}: тоо оруулна уу.",
        "msg_no_change": "Өөрчлөлт алга: шинэ утга одоогийнхтой ижил.",
        "msg_edited": "Засагдлаа {column}: {old} → {new}.",
        "ev_registered": "бүртгэсэн",
        "ev_status_changed": "төлөв өөрчилсөн",
        "ev_edited": "засвар",
    },
}

CATEGORY_NAMES = {
    "en": {
        "SLI": "Starting, lighting and ignition (SLI)",
        "EV": "Electric vehicle (EV)",
        "LMT": "Light means of transport (LMT)",
        "Stationary": "Stationary storage",
        "Industrial": "Industrial",
        "Consumer": "Portable / consumer",
    },
    "mn": {
        "SLI": "Асаагуурын батарей (SLI)",
        "EV": "Цахилгаан тээврийн хэрэгслийн (EV)",
        "LMT": "Хөнгөн тээврийн (LMT)",
        "Stationary": "Суурин хадгалалтын",
        "Industrial": "Үйлдвэрийн",
        "Consumer": "Зөөврийн / өргөн хэрэглээний",
    },
}
CHEMISTRY_NAMES = {
    "en": {"Lead-acid": "Lead-acid", "Other": "Other"},
    "mn": {"Lead-acid": "Хар тугалга-хүчил", "Other": "Бусад"},
}
STATUS_NAMES = {
    "en": {
        "original": "Original",
        "repurposed": "Repurposed",
        "re-used": "Re-used",
        "remanufactured": "Remanufactured",
        "waste": "Waste",
    },
    "mn": {
        "original": "Шинэ",
        "repurposed": "Өөр зориулалтад шилжүүлсэн",
        "re-used": "Дахин ашигласан",
        "remanufactured": "Дахин үйлдвэрлэсэн",
        "waste": "Хаягдал",
    },
}
LEVEL_NAMES = {
    "en": {"SKU": "Model (SKU)", "Batch": "Batch", "Unit": "Individual unit"},
    "mn": {"SKU": "Загвараар (SKU)", "Batch": "Багцаар", "Unit": "Ширхэгээр"},
}
KIND_NAMES = {
    "en": {
        "manufacturer": "Manufacturer",
        "importer": "Importer",
        "recycler": "Recycler",
        "repurposer": "Repurposer / second-life operator",
        "other": "Other",
    },
    "mn": {
        "manufacturer": "Үйлдвэрлэгч",
        "importer": "Импортлогч",
        "recycler": "Дахин боловсруулагч",
        "repurposer": "Дахин ашиглагч (хоёр дахь амьдрал)",
        "other": "Бусад",
    },
}

# Labels of every battery column, per language (used in the admin views,
# the correction form and the CSV).
FIELD_LABELS = {
    "id": {"en": "Battery ID", "mn": "Батарейн ID"},
    "company": {"en": "Company", "mn": "Компани"},
    "category": {"en": "Category", "mn": "Ангилал"},
    "chemistry": {"en": "Chemistry", "mn": "Химийн төрөл"},
    "weight": {"en": "Weight (kg)", "mn": "Жин (кг)"},
    "capacity": {"en": "Capacity", "mn": "Багтаамж"},
    "capacity_unit": {"en": "Capacity unit", "mn": "Багтаамжийн нэгж"},
    "voltage": {"en": "Nominal voltage (V)", "mn": "Нэрлэсэн хүчдэл (В)"},
    "capacity_kwh": {"en": "Energy (kWh)", "mn": "Энерги (кВт·цаг)"},
    "granularity": {"en": "Registration level", "mn": "Бүртгэлийн түвшин"},
    "model_id": {"en": "Model / SKU", "mn": "Загвар / SKU"},
    "batch_number": {"en": "Batch number", "mn": "Багцын дугаар"},
    "serial_number": {"en": "Serial number", "mn": "Серийн дугаар"},
    "country": {"en": "Country of manufacture", "mn": "Үйлдвэрлэсэн улс"},
    "manufacture_date": {"en": "Manufacturing date", "mn": "Үйлдвэрлэсэн огноо"},
    "status": {"en": "Lifecycle status", "mn": "Амьдралын мөчлөг"},
    "carbon_footprint": {"en": "Carbon footprint (kg CO₂e/kWh)", "mn": "Нүүрстөрөгчийн ул мөр (кг CO₂e/кВт·цаг)"},
    "recycled_content_pct": {"en": "Recycled content (%)", "mn": "Дахин боловсруулсан материал (%)"},
    "state_of_health_pct": {"en": "State of health (%)", "mn": "Эрүүл мэндийн төлөв SoH (%)"},
    "manufacturer_address": {"en": "Manufacturer address", "mn": "Үйлдвэрлэгчийн хаяг"},
    "passport_required": {"en": "Battery passport required", "mn": "Батарейн паспорт шаардлагатай эсэх"},
    "registered_at": {"en": "Registered", "mn": "Бүртгэсэн"},
}
# Order of the fields in the admin "full record" view
ADMIN_ORDER = (
    "id", "company", "category", "chemistry", "weight", "capacity",
    "capacity_unit", "voltage", "capacity_kwh", "passport_required",
    "granularity", "model_id", "batch_number", "serial_number", "country",
    "manufacture_date", "status", "carbon_footprint", "recycled_content_pct",
    "state_of_health_pct", "manufacturer_address", "registered_at",
)
# Fields an admin may correct after registration
EDITABLE_COLUMNS = (
    "company", "category", "chemistry", "weight", "capacity",
    "capacity_unit", "voltage", "granularity", "model_id", "batch_number",
    "serial_number", "country", "manufacture_date", "carbon_footprint",
    "recycled_content_pct", "state_of_health_pct", "manufacturer_address",
)
EVENT_KEYS = {
    "registered": "ev_registered",
    "status_changed": "ev_status_changed",
    "edited": "ev_edited",
}


def t(lang, key, **kw):
    """Look up a piece of text in the chosen language (English if missing)."""
    table = TEXT.get(lang) or TEXT[DEFAULT_LANG]
    value = table[key] if key in table else TEXT["en"][key]
    if kw and isinstance(value, str):
        return value.format(**kw)
    return value


def category_name(lang, code):
    return CATEGORY_NAMES.get(lang, CATEGORY_NAMES["en"]).get(code, code)


def chemistry_name(lang, code):
    return CHEMISTRY_NAMES.get(lang, CHEMISTRY_NAMES["en"]).get(code, code)


def status_name(lang, code):
    return STATUS_NAMES.get(lang, STATUS_NAMES["en"]).get(code, code)


def level_name(lang, code):
    return LEVEL_NAMES.get(lang, LEVEL_NAMES["en"]).get(code, code)


def kind_name(lang, code):
    return KIND_NAMES.get(lang, KIND_NAMES["en"]).get(code, code or "—")


def field_label(lang, column):
    return FIELD_LABELS[column].get(lang, FIELD_LABELS[column]["en"])


def category_choices(lang):
    return [(category_name(lang, c), c) for c in CATEGORIES]


def chemistry_choices(lang):
    return [(chemistry_name(lang, c), c) for c in CHEMISTRIES]


def status_choices(lang):
    return [(status_name(lang, s), s) for s in STATUSES]


def level_choices(lang):
    return [(level_name(lang, v), v) for v in LEVELS]


def kind_choices(lang):
    return [(kind_name(lang, k), k) for k in ORG_KINDS]


def field_choices(lang):
    return [(field_label(lang, c), c) for c in EDITABLE_COLUMNS]


def detect_lang(request):
    """?lang=mn / ?lang=en wins; otherwise follow the browser language."""
    if request is None:
        return DEFAULT_LANG
    try:
        asked = dict(request.query_params).get("lang", "").strip().lower()
        if asked in TEXT:
            return asked
        header = (request.headers.get("accept-language") or "").lower()
        first = header.split(",")[0].strip()
        if first.startswith("mn"):
            return "mn"
    except Exception:
        pass
    return DEFAULT_LANG


def local_time(value):
    """Show a stored timestamp in local (Ulaanbaatar) time."""
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")


# ======================================================================
# SIGN-IN, ADMIN KEY AND ATTEMPT LIMITING
# ======================================================================

FAILED_LOGINS = defaultdict(list)   # kept in memory; resets on restart
MAX_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60


class AuthError(Exception):
    """code: 'locked', 'login', 'pending' or 'admin'."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class InputError(Exception):
    """A user-facing validation message (already translated)."""


def login_locked(key):
    now = time.time()
    FAILED_LOGINS[key] = [x for x in FAILED_LOGINS[key] if now - x < LOCK_SECONDS]
    return len(FAILED_LOGINS[key]) >= MAX_ATTEMPTS


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 310000)
    return salt + ":" + digest.hex()


def password_matches(password, stored):
    try:
        salt, digest = stored.split(":", 1)
        return hmac.compare_digest(hash_password(password, salt).split(":", 1)[1], digest)
    except (ValueError, AttributeError):
        return False


def check_admin(key):
    """Raises AuthError unless the admin key is right (and not locked out)."""
    if login_locked("__admin__"):
        raise AuthError("locked")
    expected = os.getenv("REGISTRATION_KEY")
    if not expected or not hmac.compare_digest((key or "").encode("utf-8"), expected.encode("utf-8")):
        FAILED_LOGINS["__admin__"].append(time.time())
        raise AuthError("admin")


def verify_org(email, password):
    """Check an organization login; returns {'id','name','kind'} or raises."""
    email = (email or "").strip().lower()
    if login_locked(email):
        raise AuthError("locked")
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,name,password_hash,approved,kind FROM organizations WHERE email=%s",
                (email,)
            )
            record = cur.fetchone()
    if not record or not password_matches(password or "", record[2]):
        FAILED_LOGINS[email].append(time.time())
        raise AuthError("login")
    FAILED_LOGINS.pop(email, None)
    if not record[3]:
        raise AuthError("pending")
    return {"id": record[0], "name": record[1], "kind": record[4] or "other"}


def auth_message(code, lang):
    return t(lang, {
        "locked": "err_too_many", "login": "err_login",
        "pending": "err_not_approved", "admin": "err_admin_key",
    }[code])


def require_admin_key(key, lang):
    try:
        check_admin(key)
    except AuthError as error:
        raise gr.Error(auth_message(error.code, lang))


def require_session(session, lang):
    """The signed-in organization, re-checked against the database."""
    if not session:
        raise gr.Error(t(lang, "err_sign_in"))
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name,kind,approved FROM organizations WHERE id=%s", (session["id"],))
            row = cur.fetchone()
    if not row or not row[2]:
        raise gr.Error(t(lang, "err_not_approved"))
    return {"id": session["id"], "name": row[0], "kind": row[1] or "other"}


# ======================================================================
# VALIDATION (shared by the form, the CSV upload and the admin correction)
# ======================================================================

def parse_number(raw, label, lang, *, positive=False, minimum=None,
                 maximum=None, optional=False):
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if optional:
            return None
        raise InputError(t(lang, "err_required", label=label))
    if isinstance(raw, str):
        try:
            value = float(raw.strip().replace(",", "."))
        except ValueError:
            raise InputError(t(lang, "err_number", field=label))
    elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
        value = float(raw)
    else:
        raise InputError(t(lang, "err_number", field=label))
    if not math.isfinite(value):
        raise InputError(t(lang, "err_number", field=label))
    if positive and value <= 0:
        raise InputError(t(lang, "err_positive", label=label))
    if (minimum is not None and value < minimum) or (
            maximum is not None and value > maximum):
        raise InputError(t(lang, "err_range", label=label,
                           lo=fmt_number(minimum if minimum is not None else 0),
                           hi=fmt_number(maximum)))
    return value


# column -> rules for numeric columns
NUMERIC_RULES = {
    "weight": dict(positive=True, maximum=100000),
    "capacity": dict(positive=True, maximum=100000000),
    "voltage": dict(positive=True, maximum=2000, optional=True),
    "carbon_footprint": dict(minimum=0, maximum=10000, optional=True),
    "recycled_content_pct": dict(minimum=0, maximum=100, optional=True),
    "state_of_health_pct": dict(minimum=0, maximum=100, optional=True),
}
TEXT_LIMITS = {
    "company": 200, "country": 100, "model_id": 100, "batch_number": 100,
    "serial_number": 100, "manufacturer_address": 300,
}
DATE_PATTERN = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


def clean_text(raw, column, lang, *, required=False):
    value = (raw or "").strip() if isinstance(raw, str) or raw is None else str(raw).strip()
    label = field_label(lang, column)
    if required and not value:
        raise InputError(t(lang, "err_required", label=label))
    if len(value) > TEXT_LIMITS.get(column, 200):
        raise InputError(t(lang, "err_too_long", label=label, n=TEXT_LIMITS.get(column, 200)))
    return value


def compute_kwh(capacity, unit, voltage):
    """Energy in kWh: Wh / 1000, or Ah x V / 1000. None if it cannot be known."""
    if capacity is None:
        return None
    if unit == "Wh":
        return round(capacity / 1000.0, 4)
    if unit == "Ah" and voltage:
        return round(capacity * voltage / 1000.0, 4)
    return None


def passport_required(category, kwh):
    """Simplified EU rule: EV and light transport batteries, and industrial /
    stationary batteries above 2 kWh, need a battery passport from
    18 Feb 2027. Returns True, False, or None when it depends on a missing
    capacity. Check the current regulation before relying on this."""
    if category in ("EV", "LMT"):
        return True
    if category in ("Industrial", "Stationary"):
        return None if kwh is None else kwh > 2
    return False


def passport_text(lang, value):
    if value is None:
        return t(lang, "passport_unknown")
    return t(lang, "passport_yes" if value else "passport_no")


def clean_battery(data, lang):
    """Validate one battery (form row or CSV row). Raises InputError."""
    category = data.get("category")
    chemistry = data.get("chemistry")
    granularity = data.get("granularity")
    if (category not in CATEGORIES or chemistry not in CHEMISTRIES
            or granularity not in LEVELS):
        raise InputError(t(lang, "err_select_main"))
    status = data.get("status") or "original"
    unit = data.get("capacity_unit") or "Wh"
    if status not in STATUSES or unit not in CAPACITY_UNITS:
        raise InputError(t(lang, "err_select_status"))

    numbers = {
        column: parse_number(data.get(column), field_label(lang, column), lang,
                             **NUMERIC_RULES[column])
        for column in NUMERIC_RULES
    }
    if unit == "Ah" and numbers["voltage"] is None:
        raise InputError(t(lang, "err_voltage_required"))

    country = clean_text(data.get("country"), "country", lang, required=True)
    manufacture_date = (data.get("manufacture_date") or "").strip()
    if not manufacture_date:
        raise InputError(t(lang, "err_required", label=t(lang, "mfg_date")))
    if not DATE_PATTERN.fullmatch(manufacture_date):
        raise InputError(t(lang, "err_date"))

    model_id = clean_text(data.get("model_id"), "model_id", lang)
    batch_number = clean_text(data.get("batch_number"), "batch_number", lang)
    serial_number = clean_text(data.get("serial_number"), "serial_number", lang)
    # Drop identification values that this level does not use
    fields = LEVEL_FIELDS[granularity]
    if "batch_number" not in fields:
        batch_number = ""
    if "serial_number" not in fields:
        serial_number = ""
    if granularity == "SKU" and not model_id:
        raise InputError(t(lang, "err_need_model"))
    if granularity == "Batch" and not batch_number:
        raise InputError(t(lang, "err_need_batch"))
    if granularity == "Unit" and not serial_number:
        raise InputError(t(lang, "err_need_serial"))

    address = clean_text(data.get("manufacturer_address"), "manufacturer_address", lang)
    return {
        "category": category, "chemistry": chemistry,
        "weight": numbers["weight"], "capacity": numbers["capacity"],
        "capacity_unit": unit, "voltage": numbers["voltage"],
        "capacity_kwh": compute_kwh(numbers["capacity"], unit, numbers["voltage"]),
        "granularity": granularity, "model_id": model_id,
        "batch_number": batch_number, "serial_number": serial_number,
        "country": country, "manufacture_date": manufacture_date,
        "status": status,
        "carbon_footprint": numbers["carbon_footprint"],
        "recycled_content_pct": numbers["recycled_content_pct"],
        "state_of_health_pct": numbers["state_of_health_pct"],
        "manufacturer_address": address or None,
    }


def required_text(value, label, lang):
    value = (value or "").strip()
    if not value:
        raise gr.Error(t(lang, "err_required", label=label))
    return value


# Which identification fields each registration level uses:
# field -> required?  Fields not listed are hidden and left empty.
LEVEL_FIELDS = {
    "SKU": {"model_id": True},
    "Batch": {"model_id": False, "batch_number": True},
    "Unit": {"model_id": False, "batch_number": False, "serial_number": True},
}
ID_KEYS = {
    "model_id": "id_model",
    "batch_number": "id_batch",
    "serial_number": "id_serial",
}


def id_label(lang, field, level):
    """Label of an identification field; marks it optional when it is."""
    required = LEVEL_FIELDS.get(level, {}).get(field, True)
    return t(lang, ID_KEYS[field]) + ("" if required else t(lang, "optional_suffix"))


def level_hint(lang, level):
    return t(lang, f"level_hint_{level}" if level in LEVELS else "level_hint_none")


def id_field_updates(level, lang):
    """Show only the identification fields the chosen level needs."""
    fields = LEVEL_FIELDS.get(level, {})
    updates = []
    for name in ID_KEYS:
        if name in fields:
            updates.append(gr.update(visible=True, label=id_label(lang, name, level)))
        else:
            updates.append(gr.update(visible=False, value=""))
    updates.append(level_hint(lang, level))
    return updates


# ======================================================================
# DATABASE
# ======================================================================

BATTERY_COLUMNS = (
    "id", "company", "category", "chemistry", "weight", "capacity",
    "capacity_unit", "voltage", "capacity_kwh", "granularity", "model_id",
    "batch_number", "serial_number", "country", "manufacture_date", "status",
    "carbon_footprint", "recycled_content_pct", "state_of_health_pct",
    "manufacturer_address", "organization_id",
)


def init_database():
    """Creates the tables and adds any new columns. Never deletes data."""
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
                    CREATE TABLE IF NOT EXISTS organizations (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        approved BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS market_reports (
                        id BIGSERIAL PRIMARY KEY,
                        organization_id BIGINT NOT NULL REFERENCES organizations(id),
                        year INTEGER NOT NULL,
                        category TEXT NOT NULL,
                        units BIGINT NOT NULL,
                        weight_kg DOUBLE PRECISION NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (organization_id, year, category)
                    )
                """)
                # Columns added after the first versions
                for statement in (
                    "ALTER TABLE batteries ADD COLUMN IF NOT EXISTS organization_id BIGINT REFERENCES organizations(id)",
                    "ALTER TABLE batteries ADD COLUMN IF NOT EXISTS capacity_unit TEXT",
                    "ALTER TABLE batteries ADD COLUMN IF NOT EXISTS voltage DOUBLE PRECISION",
                    "ALTER TABLE batteries ADD COLUMN IF NOT EXISTS capacity_kwh DOUBLE PRECISION",
                    "ALTER TABLE batteries ADD COLUMN IF NOT EXISTS carbon_footprint DOUBLE PRECISION",
                    "ALTER TABLE batteries ADD COLUMN IF NOT EXISTS recycled_content_pct DOUBLE PRECISION",
                    "ALTER TABLE batteries ADD COLUMN IF NOT EXISTS state_of_health_pct DOUBLE PRECISION",
                    "ALTER TABLE batteries ADD COLUMN IF NOT EXISTS manufacturer_address TEXT",
                    "ALTER TABLE battery_events ADD COLUMN IF NOT EXISTS reason TEXT",
                    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS kind TEXT",
                    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS country TEXT",
                    "CREATE INDEX IF NOT EXISTS batteries_org_idx ON batteries (organization_id)",
                ):
                    cur.execute(statement)
                # Older records stored in Wh get their kWh value filled in
                cur.execute("""
                    UPDATE batteries SET capacity_kwh = capacity / 1000.0
                    WHERE capacity_kwh IS NULL AND capacity_unit = 'Wh'
                      AND capacity IS NOT NULL
                """)


def fetch_battery(cur, battery_id, lock=False):
    """One battery as a dict (or None)."""
    cur.execute(
        "SELECT " + ", ".join(BATTERY_COLUMNS)
        + ", registered_at::timestamptz FROM batteries WHERE id = %s"
        + (" FOR UPDATE" if lock else ""),
        (battery_id,)
    )
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(BATTERY_COLUMNS + ("registered_at",), row))


def insert_battery(cur, org, c):
    """Insert one validated battery and its first history event."""
    battery_id = "MCBI-" + uuid.uuid4().hex[:16].upper()
    cur.execute("""
        INSERT INTO batteries (
            id, company, category, chemistry, weight, capacity,
            capacity_unit, voltage, capacity_kwh, granularity, model_id,
            batch_number, serial_number, country, manufacture_date, status,
            carbon_footprint, recycled_content_pct, state_of_health_pct,
            manufacturer_address, organization_id
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        battery_id, org["name"], c["category"], c["chemistry"], c["weight"],
        c["capacity"], c["capacity_unit"], c["voltage"], c["capacity_kwh"],
        c["granularity"], c["model_id"], c["batch_number"],
        c["serial_number"], c["country"], c["manufacture_date"], c["status"],
        c["carbon_footprint"], c["recycled_content_pct"],
        c["state_of_health_pct"], c["manufacturer_address"], org["id"]
    ))
    cur.execute(
        "INSERT INTO battery_events (battery_id, event_type, new_value) VALUES (%s, 'registered', %s)",
        (battery_id, c["status"])
    )
    return battery_id


# ======================================================================
# LINKS, QR CODES AND ACCESS LEVELS
# ======================================================================

def record_link(battery_id):
    """The permanent address printed in the QR code."""
    return f"{PORTAL_URL}/b/{quote(battery_id, safe='')}"


def json_link(battery_id):
    return f"{PORTAL_URL}/api/v1/batteries/{quote(battery_id, safe='')}"


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


# Three access levels, as in the EU Battery Regulation:
#   public    - anyone who scans the QR code
#   interest  - recyclers and second-life operators (and the owner of the
#               record); needs an approved organization login
#   authority - MCBI administrators / authorities; needs the admin key
# PROVISIONAL: the EU implementing act that names the "persons with a
# legitimate interest" and the exact Annex XIII split is still being settled.
# To change what a level sees, edit this table only.
FIELD_ACCESS = {
    "id": "public", "category": "public", "chemistry": "public",
    "status": "public", "registered_at": "public",
    "passport_required": "public", "capacity_kwh": "public",
    "carbon_footprint": "public", "recycled_content_pct": "public",
    "company": "interest", "manufacturer_address": "interest",
    "granularity": "interest", "model_id": "interest",
    "batch_number": "interest", "serial_number": "interest",
    "country": "interest", "manufacture_date": "interest",
    "weight": "interest", "capacity": "interest", "capacity_unit": "interest",
    "voltage": "interest", "state_of_health_pct": "interest",
}
LEVEL_RANK = {"public": 0, "interest": 1, "authority": 2}

# JSON layout: the group names follow the Battery Pass data model categories
JSON_GROUPS = {
    "generalProductInformation": (
        "id", "category", "chemistry", "status", "registered_at",
        "passport_required", "company", "manufacturer_address",
        "granularity", "model_id", "batch_number", "serial_number",
        "country", "manufacture_date",
    ),
    "carbonFootprint": ("carbon_footprint",),
    "circularity": ("recycled_content_pct",),
    "performanceAndDurability": (
        "capacity", "capacity_unit", "capacity_kwh", "voltage", "weight",
        "state_of_health_pct",
    ),
}
JSON_NAMES = {
    "id": "batteryId", "company": "manufacturer",
    "registered_at": "registeredAt", "passport_required": "passportRequired",
    "manufacturer_address": "manufacturerAddress", "model_id": "modelId",
    "batch_number": "batchNumber", "serial_number": "serialNumber",
    "manufacture_date": "manufactureDate", "carbon_footprint": "carbonFootprintKgCo2ePerKwh",
    "recycled_content_pct": "recycledContentPercent",
    "capacity_kwh": "energyKwh", "capacity_unit": "capacityUnit",
    "state_of_health_pct": "stateOfHealthPercent", "voltage": "nominalVoltageV",
    "granularity": "registrationLevel", "weight": "weightKg",
}


def json_name(column):
    return JSON_NAMES.get(column, column)


def battery_json(b, level, history=None):
    """The record as JSON, limited to what the access level may see."""
    rank = LEVEL_RANK[level]
    data = dict(b)
    data["passport_required"] = passport_required(b["category"], b["capacity_kwh"])
    if data["registered_at"] is not None:
        data["registered_at"] = data["registered_at"].astimezone(timezone.utc).isoformat()
    groups = {}
    for group, columns in JSON_GROUPS.items():
        groups[group] = {
            json_name(column): data[column]
            for column in columns
            if LEVEL_RANK[FIELD_ACCESS[column]] <= rank
        }
    result = {
        "schema": "MCBI battery record v0.1 (field groups follow the Battery Pass data model categories; access classification is provisional)",
        "accessLevel": level,
        **groups,
        "links": {"record": record_link(b["id"]), "json": json_link(b["id"])},
    }
    if level == "authority" and history is not None:
        result["history"] = history
    return result


# ======================================================================
# HTML BUILDING BLOCKS (all user text is escaped)
# ======================================================================

def esc(value):
    if value is None or value == "":
        return "—"
    return html.escape(str(value))


def fmt_number(value):
    if value is None:
        return "—"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def lifecycle_html(status, lang):
    stage = {
        "original": 0, "re-used": 1, "repurposed": 1,
        "remanufactured": 1, "waste": 2,
    }.get(status, 0)
    steps = (t(lang, "life_1"), t(lang, "life_2"), t(lang, "life_3"))
    items = []
    for index, text in enumerate(steps):
        state = (
            "done" if index < stage
            else "current" if index == stage
            else "todo"
        )
        items.append(f'<li class="mcbi-step-{state}"><span></span>{text}</li>')
    return '<ol class="mcbi-life">' + "".join(items) + "</ol>"


def waste_note(lang):
    return f"""
<div class="mcbi-note">
  <svg width="26" height="30" viewBox="0 0 30 34" aria-hidden="true">
    <path d="M8 9h14l-1.5 19h-11z" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linejoin="round"/>
    <path d="M6 9h18M12 9V6h6v3" fill="none" stroke="currentColor"
          stroke-width="2" stroke-linecap="round"/>
    <path d="M3 4l24 27M27 4L3 31" stroke="currentColor" stroke-width="2"
          stroke-linecap="round"/>
  </svg>
  <div><strong>{t(lang, "waste_title")}</strong>
  {t(lang, "waste_text")}</div>
</div>
"""


def detail_cells(rows):
    """<dl> grid from (label, value) pairs; empty values are skipped."""
    cells = "".join(
        f'<div><dt>{label}</dt><dd>{esc(value)}</dd></div>'
        for label, value in rows if value not in (None, "")
    )
    return f'<dl class="mcbi-grid">{cells}</dl>' if cells else ""


def public_rows(b, lang):
    kwh = b["capacity_kwh"]
    rows = [
        (t(lang, "energy_word"), f"{fmt_number(kwh)} kWh" if kwh is not None else None),
        (t(lang, "passport_word"), passport_text(lang, passport_required(b["category"], kwh))),
    ]
    if b["carbon_footprint"] is not None:
        rows.append((t(lang, "carbon_word"), f"{fmt_number(b['carbon_footprint'])} kg CO₂e/kWh"))
    if b["recycled_content_pct"] is not None:
        rows.append((t(lang, "recycled_word"), f"{fmt_number(b['recycled_content_pct'])} %"))
    return rows


def public_card(b, lang):
    battery_id = b["id"]
    qr = image_data_uri(make_qr(battery_id))
    registered = local_time(b["registered_at"])
    return f"""
<div class="mcbi-passport">
  <div class="mcbi-passport-dark">
    <span class="mcbi-eyebrow">{t(lang, "pp_eyebrow")}</span>
    <span class="mcbi-big">{esc(chemistry_name(lang, b["chemistry"]))} {t(lang, "battery_word")}</span>
    <span class="mcbi-muted-light">{esc(category_name(lang, b["category"]))}</span>
    <span class="mcbi-id">{esc(battery_id)}</span>
    <img class="mcbi-qr" src="{qr}" alt="{t(lang, "qr_alt")}">
  </div>
  <div class="mcbi-passport-body">
    <div class="mcbi-row">
      <span class="mcbi-label">{t(lang, "lifecycle")}</span>
      <span class="mcbi-chip">{esc(status_name(lang, b["status"]))}</span>
    </div>
    {lifecycle_html(b["status"], lang)}
    {detail_cells(public_rows(b, lang))}
    <span class="mcbi-small">{t(lang, "registered")}: {esc(registered)} ·
      <a href="{html.escape(json_link(battery_id))}" target="_blank" rel="noopener">{t(lang, "json_word")}</a></span>
    {waste_note(lang)}
    <p class="mcbi-small">{t(lang, "public_note")}</p>
  </div>
</div>
"""


def private_card(values, qr_image, lang):
    qr = image_data_uri(qr_image)
    kwh = values.get("capacity_kwh")
    rows = [
        (t(lang, "company"), values["company"]),
        (t(lang, "serial"), values["serial_number"]),
        (t(lang, "model"), values["model_id"]),
        (t(lang, "batch"), values["batch_number"]),
        (t(lang, "weight_word"), f"{fmt_number(values['weight'])} {t(lang, 'kg')}"),
        (t(lang, "voltage_word"), f"{fmt_number(values['voltage'])} V" if values.get("voltage") else None),
        (t(lang, "energy_word"), f"{fmt_number(kwh)} kWh" if kwh is not None else None),
        (t(lang, "passport_word"), passport_text(lang, passport_required(values["category"], kwh))),
        (t(lang, "carbon_word"), f"{fmt_number(values['carbon_footprint'])} kg CO₂e/kWh" if values.get("carbon_footprint") is not None else None),
        (t(lang, "recycled_word"), f"{fmt_number(values['recycled_content_pct'])} %" if values.get("recycled_content_pct") is not None else None),
        (field_label(lang, "state_of_health_pct"), f"{fmt_number(values['state_of_health_pct'])} %" if values.get("state_of_health_pct") is not None else None),
        (t(lang, "made"), f"{values['country']} · {values['manufacture_date']}"),
        (t(lang, "level"), level_name(lang, values["granularity"])),
        (t(lang, "registered"), values["registered"]),
    ]
    return f"""
<div class="mcbi-success">
  <span class="mcbi-tick" aria-hidden="true">✓</span>
  <div><strong>{t(lang, "success_title")}</strong>
  {t(lang, "success_text")}</div>
</div>
<div class="mcbi-passport">
  <div class="mcbi-passport-dark">
    <img class="mcbi-qr" src="{qr}" alt="{t(lang, "qr_alt")}">
    <span class="mcbi-eyebrow">{t(lang, "battery_id_caps")}</span>
    <span class="mcbi-id">{esc(values['battery_id'])}</span>
  </div>
  <div class="mcbi-passport-body">
    <div class="mcbi-row">
      <span class="mcbi-eyebrow-dark">{t(lang, "pp_eyebrow")}</span>
      <span class="mcbi-chip">{esc(status_name(lang, values['status']))}</span>
    </div>
    <span class="mcbi-big-dark">{esc(values['chemistry'])} ·
      {esc(fmt_number(values['capacity']))} {esc(values['capacity_unit'])}</span>
    <span class="mcbi-muted">{esc(category_name(lang, values['category']))}</span>
    {detail_cells(rows)}
    <p class="mcbi-small">{t(lang, "private_note")}</p>
  </div>
</div>
"""


def message_card(text):
    return f'<div class="mcbi-empty">{text}</div>'


def lookup_empty(lang):
    return message_card(t(lang, "lookup_empty"))


def md_table(headers, rows):
    def cell(value):
        return str(value).replace("|", "/").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


# ======================================================================
# ACTIONS: ORGANIZATIONS AND SIGN-IN
# ======================================================================

def create_organization(name, email, password, kind, country, lang):
    name = required_text(name, t(lang, "org_name"), lang)
    email = required_text(email, t(lang, "org_email"), lang).lower()
    country = required_text(country, t(lang, "org_country"), lang)
    if kind not in ORG_KINDS:
        raise gr.Error(t(lang, "err_select_kind"))
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise gr.Error(t(lang, "err_email"))
    if len(password or "") < 12:
        raise gr.Error(t(lang, "err_password_short"))
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM organizations WHERE email=%s", (email,))
                if cur.fetchone():
                    raise gr.Error(t(lang, "err_org_exists"))
                cur.execute(
                    "INSERT INTO organizations (name,email,password_hash,kind,country) VALUES (%s,%s,%s,%s,%s)",
                    (name[:200], email, hash_password(password), kind, country[:100])
                )
    return t(lang, "msg_org_submitted")


def account_views(session, lang):
    """(login box, account bar, account text) for the signed-in state."""
    if session:
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            t(lang, "signed_in_as", name=session["name"],
              kind=kind_name(lang, session["kind"])),
        )
    return gr.update(visible=True), gr.update(visible=False), ""


def sign_in(email, password, lang):
    try:
        org = verify_org(email, password)
    except AuthError as error:
        raise gr.Error(auth_message(error.code, lang))
    return (org, *account_views(org, lang), gr.update(value=""))


def sign_out(lang):
    return (None, *account_views(None, lang))


def list_organizations(admin_key, lang):
    require_admin_key(admin_key, lang)
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,name,email,approved,kind,country FROM organizations ORDER BY id DESC LIMIT 100")
            rows = cur.fetchall()
    approved_word = t(lang, "org_approved_word")
    pending_word = t(lang, "org_pending_word")
    return "\n".join(
        f"ID {i} | {name} | {email} | {kind_name(lang, kind) if kind else '—'} | "
        f"{country or '—'} | {approved_word if approved else pending_word}"
        for i, name, email, approved, kind, country in rows
    ) or t(lang, "msg_no_orgs")


def approve_organization(org_id, admin_key, lang):
    require_admin_key(admin_key, lang)
    try:
        org_id = int(org_id)
    except (ValueError, TypeError):
        raise gr.Error(t(lang, "err_org_id"))
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE organizations SET approved=TRUE WHERE id=%s RETURNING name", (org_id,))
                row = cur.fetchone()
                if not row:
                    raise gr.Error(t(lang, "err_org_missing"))
    return t(lang, "msg_org_approved", name=row[0])


# ======================================================================
# ACTIONS: REGISTERING BATTERIES
# ======================================================================

def register_battery(
    session, category, chemistry, weight, capacity, capacity_unit, voltage,
    granularity, model_id, batch_number, serial_number, country,
    manufacture_date, status, carbon, recycled, soh, address, lang
):
    org = require_session(session, lang)
    try:
        c = clean_battery({
            "category": category, "chemistry": chemistry, "weight": weight,
            "capacity": capacity, "capacity_unit": capacity_unit,
            "voltage": voltage, "granularity": granularity,
            "model_id": model_id, "batch_number": batch_number,
            "serial_number": serial_number, "country": country,
            "manufacture_date": manufacture_date, "status": status,
            "carbon_footprint": carbon, "recycled_content_pct": recycled,
            "state_of_health_pct": soh, "manufacturer_address": address,
        }, lang)
    except InputError as error:
        raise gr.Error(str(error))

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                battery_id = insert_battery(cur, org, c)

    qr = make_qr(battery_id)
    values = dict(c, battery_id=battery_id, company=org["name"],
                  registered=datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M"))
    return (
        gr.update(visible=True),
        private_card(values, qr, lang),
        battery_id,
        record_link(battery_id),
        gr.update(value=save_qr_file(battery_id, qr)),
        values,  # kept so the card can be redrawn if the language changes
    )


def reset_registration_results():
    """Hide the previous result so the next battery starts clean."""
    return gr.update(visible=False), "", "", "", gr.update(value=None), {}


def clear_battery_fields():
    # order: category, chemistry, weight, capacity, unit, voltage, level,
    # model, batch, serial, country, date, status, carbon, recycled, soh,
    # address
    return (
        None, None, None, None, "Wh", None,
        None, "", "", "",
        "", "", "original", None, None, None, ""
    )


# ======================================================================
# ACTIONS: CSV (template, bulk upload, exports)
# ======================================================================

CSV_COLUMNS = (
    "category", "chemistry", "weight_kg", "capacity", "capacity_unit",
    "voltage_v", "level", "model_id", "batch_number", "serial_number",
    "country", "manufacture_date", "status", "carbon_footprint",
    "recycled_content_pct", "state_of_health_pct", "manufacturer_address",
)
CSV_TO_FIELD = {
    "weight_kg": "weight", "voltage_v": "voltage", "level": "granularity",
}
CSV_ALIASES = {  # other header names that are accepted
    "weight": "weight_kg", "voltage": "voltage_v", "granularity": "level",
    "registration_level": "level", "unit": "capacity_unit",
}
CSV_REQUIRED = ("category", "chemistry", "weight_kg", "capacity", "level",
                "country", "manufacture_date")
CSV_EXAMPLE = (
    "EV", "NMC", "450", "75000", "Wh", "", "Unit", "Model-X", "",
    "SN-0001", "Czech Republic", "2026-09", "original", "", "", "", "",
)


def temp_file(name):
    folder = tempfile.mkdtemp(prefix="mcbi_")
    return os.path.join(folder, name)


def csv_safe(value):
    """Stops spreadsheet programs from running text that starts with = + - @."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in rows:
            writer.writerow([csv_safe(v) if v is not None else "" for v in row])


def csv_template(lang):
    path = temp_file("mcbi_battery_template.csv")
    write_csv(path, CSV_COLUMNS, [CSV_EXAMPLE])
    return path


def read_csv_rows(file_path, lang):
    """Rows of the uploaded CSV as dicts keyed by our column names."""
    if not file_path:
        raise gr.Error(t(lang, "err_no_file"))
    try:
        if os.path.getsize(file_path) > MAX_CSV_BYTES:
            raise gr.Error(t(lang, "err_csv_read"))
        raw = open(file_path, "rb").read()
    except OSError:
        raise gr.Error(t(lang, "err_csv_read"))
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        raise gr.Error(t(lang, "err_csv_read"))
    first_line = text.splitlines()[0] if text.strip() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        raise gr.Error(t(lang, "err_csv_empty"))
    names = []
    for name in header:
        name = name.strip().lower().replace(" ", "_")
        names.append(CSV_ALIASES.get(name, name))
    missing = [c for c in CSV_REQUIRED if c not in names]
    if missing:
        raise gr.Error(t(lang, "err_csv_cols", cols=", ".join(missing)))
    rows = []
    for number, values in enumerate(reader, start=2):
        if not any(v.strip() for v in values):
            continue
        rows.append((number, dict(zip(names, values))))
    if not rows:
        raise gr.Error(t(lang, "err_csv_empty"))
    if len(rows) > MAX_CSV_ROWS:
        raise gr.Error(t(lang, "err_csv_too_many", n=len(rows), max=MAX_CSV_ROWS))
    return rows


def bulk_register(session, file_path, lang):
    org = require_session(session, lang)
    rows = read_csv_rows(file_path, lang)

    cleaned, problems = [], []
    for number, raw in rows:
        data = {CSV_TO_FIELD.get(k, k): (v or "").strip() for k, v in raw.items()}
        data["status"] = data.get("status") or "original"
        data["capacity_unit"] = data.get("capacity_unit") or "Wh"
        # accept "ev", "lfp", "unit" ... in any letter case
        for field, options in (
            ("category", CATEGORIES), ("chemistry", CHEMISTRIES),
            ("granularity", LEVELS), ("capacity_unit", CAPACITY_UNITS),
            ("status", STATUSES),
        ):
            given = data.get(field, "")
            data[field] = next(
                (o for o in options if o.lower() == given.lower()), given)
        try:
            cleaned.append((number, clean_battery(data, lang)))
        except InputError as error:
            problems.append(t(lang, "msg_csv_row", n=number, msg=str(error)))
    if problems:
        return "\n".join([t(lang, "msg_csv_errors")] + problems[:100]), None

    created = []
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                for number, c in cleaned:
                    created.append((number, insert_battery(cur, org, c), c))

    path = temp_file(f"mcbi_registered_{datetime.now(LOCAL_TZ):%Y%m%d_%H%M%S}.zip")
    table = io.StringIO()
    writer = csv.writer(table)
    writer.writerow(["row", "battery_id", "link", "model_id", "batch_number", "serial_number"])
    for number, battery_id, c in created:
        writer.writerow([number, battery_id, record_link(battery_id),
                         csv_safe(c["model_id"]), csv_safe(c["batch_number"]),
                         csv_safe(c["serial_number"])])
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("registered.csv", "﻿" + table.getvalue())
        for _number, battery_id, _c in created:
            image = io.BytesIO()
            make_qr(battery_id).save(image, format="PNG")
            archive.writestr(f"qr/{battery_id}.png", image.getvalue())
    return t(lang, "msg_csv_done", n=len(created)), path


EXPORT_HEADER = (
    "battery_id", "company", "category", "chemistry", "weight_kg", "capacity",
    "capacity_unit", "voltage_v", "energy_kwh", "level", "model_id",
    "batch_number", "serial_number", "country", "manufacture_date", "status",
    "carbon_footprint", "recycled_content_pct", "state_of_health_pct",
    "manufacturer_address", "registered_at", "link",
)


def export_rows(where, params):
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM batteries " + where + " ORDER BY registered_at, id",
                params
            )
            ids = [row[0] for row in cur.fetchall()]
            records = [fetch_battery(cur, i) for i in ids]
    return [
        (b["id"], b["company"], b["category"], b["chemistry"], b["weight"],
         b["capacity"], b["capacity_unit"], b["voltage"], b["capacity_kwh"],
         b["granularity"], b["model_id"], b["batch_number"],
         b["serial_number"], b["country"], b["manufacture_date"], b["status"],
         b["carbon_footprint"], b["recycled_content_pct"],
         b["state_of_health_pct"], b["manufacturer_address"],
         local_time(b["registered_at"]), record_link(b["id"]))
        for b in records if b
    ]


def export_mine(session, lang):
    org = require_session(session, lang)
    path = temp_file(f"mcbi_my_batteries_{datetime.now(LOCAL_TZ):%Y%m%d}.csv")
    write_csv(path, EXPORT_HEADER,
              export_rows("WHERE organization_id = %s", (org["id"],)))
    return path


def export_all(admin_key, lang):
    require_admin_key(admin_key, lang)
    path = temp_file(f"mcbi_all_batteries_{datetime.now(LOCAL_TZ):%Y%m%d}.csv")
    write_csv(path, EXPORT_HEADER, export_rows("", ()))
    return path


# ======================================================================
# ACTIONS: EPR MARKET REPORTS
# ======================================================================

def reports_table(org_id, lang):
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT year, category, units, weight_kg FROM market_reports
                WHERE organization_id = %s ORDER BY year DESC, category
            """, (org_id,))
            rows = cur.fetchall()
    if not rows:
        return t(lang, "msg_no_reports")
    body = [(y, category_name(lang, c), u, fmt_number(w)) for y, c, u, w in rows]
    body.append((t(lang, "th_total"), "", sum(r[2] for r in rows),
                 fmt_number(sum(r[3] for r in rows))))
    return md_table((t(lang, "th_year"), t(lang, "th_category"),
                     t(lang, "th_units"), t(lang, "th_weight")), body)


def whole_number(raw, label, lang):
    value = parse_number(raw, label, lang, minimum=0)
    if value != int(value):
        raise InputError(t(lang, "err_int", label=label))
    return int(value)


def save_report(session, year, category, units, weight, lang):
    org = require_session(session, lang)
    try:
        year = whole_number(year, t(lang, "epr_year"), lang)
        if not 2020 <= year <= 2100:
            raise InputError(t(lang, "err_year"))
        if category not in CATEGORIES:
            raise InputError(t(lang, "err_select_main"))
        units = whole_number(units, t(lang, "epr_units"), lang)
        weight = parse_number(weight, t(lang, "epr_weight"), lang, minimum=0,
                              maximum=1e9)
    except InputError as error:
        raise gr.Error(str(error))
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO market_reports (organization_id, year, category, units, weight_kg)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (organization_id, year, category)
                    DO UPDATE SET units = EXCLUDED.units,
                                  weight_kg = EXCLUDED.weight_kg,
                                  updated_at = CURRENT_TIMESTAMP
                """, (org["id"], year, category, units, weight))
    saved = t(lang, "msg_report_saved", year=year,
              category=category_name(lang, category), units=units,
              weight=fmt_number(weight))
    return saved, reports_table(org["id"], lang)


def show_reports(session, lang):
    org = require_session(session, lang)
    return reports_table(org["id"], lang)


def market_summary(admin_key, lang):
    require_admin_key(admin_key, lang)
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT year, category, SUM(units), SUM(weight_kg),
                       COUNT(DISTINCT organization_id)
                FROM market_reports GROUP BY year, category
                ORDER BY year DESC, category
            """)
            rows = cur.fetchall()
    if not rows:
        return t(lang, "msg_no_reports")
    body = [(y, category_name(lang, c), int(u), fmt_number(float(w)), n)
            for y, c, u, w, n in rows]
    return md_table((t(lang, "th_year"), t(lang, "th_category"),
                     t(lang, "th_units"), t(lang, "th_weight"),
                     t(lang, "th_orgs")), body)


# ======================================================================
# ACTIONS: LOOKUP AND ADMIN
# ======================================================================

def find_battery(battery_id, lang):
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return lookup_empty(lang), gr.update(value="", visible=False)

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            b = fetch_battery(cur, battery_id)

    if b is None:
        return (
            message_card(t(lang, "lookup_notfound")),
            gr.update(value="", visible=False),
        )

    return public_card(b, lang), gr.update(
        value=record_link(b["id"]), visible=True
    )


def admin_find_battery(battery_id, admin_key, lang):
    require_admin_key(admin_key, lang)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return t(lang, "err_enter_id")

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            b = fetch_battery(cur, battery_id)

    if b is None:
        return t(lang, "err_battery_missing")

    b["passport_required"] = passport_text(
        lang, passport_required(b["category"], b["capacity_kwh"]))
    b["registered_at"] = local_time(b["registered_at"])
    return "\n".join(
        f"{field_label(lang, column)}: {b[column] if b[column] is not None else '—'}"
        for column in ADMIN_ORDER
    )


def admin_list_batteries(admin_key, lang):
    require_admin_key(admin_key, lang)

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
        return t(lang, "msg_no_batteries")

    rows = [t(lang, "list_header", total=total, n=len(records))]

    rows.extend(
        f"{battery_id} | {company or '—'} | "
        f"{category or '—'} | {model_id or '—'} | "
        f"{status or '—'} | {local_time(registered_at)}"
        for battery_id, company, category, model_id, status, registered_at
        in records
    )

    return "\n".join(rows)


def change_status(battery_id, new_status, reason, admin_key, lang):
    require_admin_key(admin_key, lang)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id or new_status not in STATUSES:
        raise gr.Error(t(lang, "err_status_inputs"))

    reason = required_text(reason, t(lang, "reason"), lang)

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
                    raise gr.Error(t(lang, "err_battery_missing"))

                old_status = row[0]

                if old_status == new_status:
                    return t(lang, "msg_status_same")

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

    return t(lang, "msg_status_updated", old=old_status, new=new_status)


def battery_history(cur, battery_id):
    cur.execute("""
        SELECT event_type, old_value, new_value, reason, occurred_at
        FROM battery_events WHERE battery_id = %s ORDER BY id
    """, (battery_id,))
    return cur.fetchall()


def admin_history(battery_id, admin_key, lang):
    require_admin_key(admin_key, lang)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return t(lang, "err_enter_id")

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            events = battery_history(cur, battery_id)

    if not events:
        return t(lang, "msg_no_history")

    return "\n".join(
        f"{local_time(occurred_at)}: "
        f"{t(lang, EVENT_KEYS[event_type]) if event_type in EVENT_KEYS else event_type} "
        f"({old or '—'} → {new or '—'})"
        + (f" — {reason}" if reason else "")
        for event_type, old, new, reason, occurred_at
        in events
    )


ENUM_FIELDS = {
    "category": CATEGORIES,
    "chemistry": CHEMISTRIES,
    "granularity": LEVELS,
    "capacity_unit": CAPACITY_UNITS,
}


def clean_column(column, raw, lang):
    """Validate one corrected value; returns what to store (None clears)."""
    label = field_label(lang, column)
    raw = (raw or "").strip()
    if column in NUMERIC_RULES:
        return parse_number(raw, label, lang, **NUMERIC_RULES[column])
    if column in ENUM_FIELDS:
        if raw not in ENUM_FIELDS[column]:
            raise InputError(t(lang, "err_allowed", field=label,
                               values=", ".join(ENUM_FIELDS[column])))
        return raw
    if column == "manufacture_date":
        if not DATE_PATTERN.fullmatch(raw):
            raise InputError(t(lang, "err_date"))
        return raw
    if column == "manufacturer_address":
        return clean_text(raw, column, lang) or None
    return clean_text(raw, column, lang, required=column in ("company", "country"))


def edit_battery(battery_id, column, new_value, reason, admin_key, lang):
    require_admin_key(admin_key, lang)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        raise gr.Error(t(lang, "err_enter_id"))
    if column not in EDITABLE_COLUMNS:
        raise gr.Error(t(lang, "err_select_field"))

    reason = required_text(reason, t(lang, "reason"), lang)
    try:
        new_value = clean_column(column, new_value, lang)
    except InputError as error:
        raise gr.Error(str(error))

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                # column comes from the fixed EDITABLE_COLUMNS whitelist
                b = fetch_battery(cur, battery_id, lock=True)
                if b is None:
                    raise gr.Error(t(lang, "err_battery_missing"))
                old_value = b[column]

                if old_value == new_value or str(old_value) == str(new_value):
                    return t(lang, "msg_no_change")

                cur.execute(
                    f"UPDATE batteries SET {column} = %s WHERE id = %s",
                    (new_value, battery_id)
                )
                if column in ("capacity", "capacity_unit", "voltage"):
                    b[column] = new_value
                    cur.execute(
                        "UPDATE batteries SET capacity_kwh = %s WHERE id = %s",
                        (compute_kwh(b["capacity"], b["capacity_unit"], b["voltage"]),
                         battery_id)
                    )
                cur.execute("""
                    INSERT INTO battery_events (
                        battery_id, event_type, old_value, new_value, reason
                    )
                    VALUES (%s, 'edited', %s, %s, %s)
                """, (
                    battery_id,
                    f"{column}: {old_value if old_value is not None else '—'}",
                    f"{column}: {new_value if new_value is not None else '—'}",
                    reason
                ))

    return t(lang, "msg_edited", column=field_label(lang, column),
             old=old_value if old_value is not None else "—",
             new=new_value if new_value is not None else "—")


def load_battery_from_url(request: gr.Request):
    """Runs when the page opens: picks the language and any ?battery_id=."""
    lang = detect_lang(request)
    battery_id = (
        dict(request.query_params).get("battery_id", "")
        if request else ""
    )
    battery_id = battery_id.strip().upper()

    if not battery_id:
        return lang, "", lookup_empty(lang), gr.update(value="", visible=False)

    card, link = find_battery(battery_id, lang)
    return lang, battery_id, card, link


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

# Keeps ?lang=... in the address bar so a shared link opens in that language.
LANG_URL_JS = """
(lang) => {
    const url = new URL(window.location.href);
    url.searchParams.set("lang", lang);
    window.history.replaceState(null, "", url);
    return [];
}
"""

SCROLL_TOP_JS = "() => { window.scrollTo({top: 0, behavior: 'smooth'}); return []; }"


# ======================================================================
# WEB ADDRESSES FOR QR CODES AND MACHINES
#   /b/<ID>                  permanent address printed in the QR code
#   /api/v1/batteries/<ID>   the record as JSON (3 access levels)
#   /healthz                 for the hosting platform's health check
# ======================================================================

api = FastAPI(title="MCBI EPR Portal", docs_url=None, redoc_url=None)


@api.get("/healthz")
def healthz():
    return {"status": "ok"}


@api.get("/b/{battery_id}")
def resolve_battery(battery_id: str, request: Request):
    """Browsers get the portal page, machines asking for JSON get the data."""
    battery_id = battery_id.strip().upper()
    if "application/json" in (request.headers.get("accept") or ""):
        return RedirectResponse(f"/api/v1/batteries/{quote(battery_id, safe='')}", status_code=302)
    target = f"/?battery_id={quote(battery_id, safe='')}"
    asked = request.query_params.get("lang", "").lower()
    if asked in TEXT:
        target += f"&lang={asked}"
    return RedirectResponse(target, status_code=302)


def api_error(status, message):
    return JSONResponse({"error": message}, status_code=status,
                        headers={"Cache-Control": "no-store"})


@api.get("/api/v1/batteries/{battery_id}")
def api_battery(battery_id: str, request: Request):
    battery_id = battery_id.strip().upper()
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            b = fetch_battery(cur, battery_id)
            history = None
            if b is not None:
                history = [
                    {"time": when.astimezone(timezone.utc).isoformat(),
                     "event": kind, "from": old, "to": new, "reason": reason}
                    for kind, old, new, reason, when in battery_history(cur, battery_id)
                ]
    if b is None:
        return api_error(404, "battery not found")

    level = "public"
    admin_key = request.headers.get("x-admin-key")
    authorization = request.headers.get("authorization") or ""
    try:
        if admin_key:
            check_admin(admin_key)
            level = "authority"
        elif authorization.lower().startswith("basic "):
            try:
                email, _, password = base64.b64decode(
                    authorization[6:]).decode("utf-8").partition(":")
            except Exception:
                return api_error(401, "invalid Authorization header")
            org = verify_org(email, password)
            if org["id"] == b["organization_id"] or org["kind"] in INTEREST_KINDS:
                level = "interest"
    except AuthError as error:
        status = {"locked": 429, "login": 401, "admin": 401, "pending": 403}[error.code]
        return api_error(status, {
            "locked": "too many failed attempts, try again later",
            "login": "incorrect email or password",
            "admin": "incorrect admin key",
            "pending": "organization is awaiting approval",
        }[error.code])

    headers = {"Cache-Control": "public, max-age=60" if level == "public" else "no-store"}
    return JSONResponse(battery_json(b, level, history), headers=headers)


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

# The MCBI logo, embedded in the page. Leave empty to show no logo.
LOGO_URI = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGAAAABgBAMAAAAQtmoLAAABWGlDQ1BJQ0MgUHJvZmlsZQAAeJx9kLFLw1AQxr9WpaB1EB0cHDKJQ5SSCro4tBVEcQhVweqUvqapkMZHkiIFN/+Bgv+BCs5uFoc6OjgIopPo5uSk4KLleS+JpCJ6j+N+fO+74zggOW5wbvcDqDu+W1zKK5ulLSX1jAS9IAzm8Zyur0r+rj/j/T703k7LWb///43Biukxqp+UGcZdH0ioxPqezyXvE4+5tBRxS7IV8onkcsjngWe9WCC+JlZYzagQvxCr5R7d6uG63WDRDnL7tOlsrMk5lBNYxA48cNgw0IQCHdk//LOBv4BdcjfhUp+FGnzqyZEiJ5jEy3DAMAOVWEOGUpN3ju53F91PjbWDJ2ChI4S4iLWVDnA2Rydrx9rUPDAyBFy1ueEagdRHmaxWgddTYLgEjN5Qz7ZXzWrh9uk8MPAoxNskkDoEui0hPo6E6B5T8wNw6XwBA6diE8HYWhMAAAAwUExURQ0hUvT09gAAAZObsGBtjTZHb7G3xgMMYEdWenqFngAFOwkcTrzBzgofUAADNwAGOwGJW2AAAAAQdFJOU/7+AP7+/v4M/v7+n/5aX5QJ5Z3iAAAKhklEQVR42oWYe3BU1R3HP/e12XWTcA8baBA1y6qjFiS7JRXEAotofQThhjQVlWmTYh07o06KY+uMzriUPrTVEnzXacdYoUVRudqm1Vp1M/hoRXExgFF5rBJehrBrEswm+7j949yFbAC7/9y995zf+/y+v9/vKCFKf0YWmjzNuwmNtG8Ayx6zrowhsGxumHu5+/LqGfUY2a8laNrQdLGFPi1hLHv5AOB/r37f5JIdain/DdfdZ2lV6w+y0M40oz9+9IJHJhslWzRRos8rTUDZV3sHfZN6ypPjXvNm1j1nG4VTSGiyXzh3VQCVN/KE60+zNP8KDRb01jedyoYXwj4vzuD4LKnIuC/3fFn1u5+mlDeiFRNOLsG6LkzGSetKPgpmF5C9EdosBh4xTkZgvforiFqami38E2tTIRlGz6vEwnDVBuMkBB2r9EmYHWvhhkzKzqVScT1v5n3Ewbq4/iReei66eOes1/V9h7561/1SyNXuzJd/hX7oy23+sRIMf3hpE4kREtMAll522ZUWuXeI6pCHAdsa4yVr7vcq6rYUUt47Y+iztktm33oVvUI7HFkdxX9GtkQlY89DuucgtWZPnDXv9PrPXNH/k3Ef7fdfsSPnfeKvj0P2SW/3aAnWXAsRTPbPiRvTkuCkAcUE/zlxlMBhvLM2uyJcG16xINpjPxY3liUBq7h0dGsUFqL7Pj76uxIbfm+BPv5IjkgS4J5WQK8AMGbb6BWoff5vjJLgt4Dc5IU0JAGIA+QAyL4Jr5HOc9Q+LsEqtMlk83ml3BQAndKVi9sbKxNOgorTs4AOGB0fS2acnxxtWEI+XrSe9/jnJRiox3bX9GJQku6T44oB/0FTbSBaZFa/zl0x3afUnmL+D8dyKsANHdIGg49dxkWCxe0yqJXuu94rnyuwUUdpVNyvtTd5tHBzU76/VCJRKcH6QbiEoXa4TWld8vmneqps2P3kpAGoOD2LCobcz9zi/vCqVsIOuenDZcUTJx8DFqjwD/eAu148HOuZTlOcJg7MLQwGZWbE5NoNoIQoJEebXHPnzZF4U5+Fsm293rf47xWjdSqbjA62VKktBqDeWT0lfunuPVsIjj9n5/iGkaHEKJ08oAlr3HoA/gvAWQ//Y/eCrX3OktzuAzUt7+kbesoAnAwAIxMLqtFhjbJLba3qXb0t35i6YtvqbyVePrRx5felFa5j6i0l5JP5qHxjDmRt5jvbztQ363Xvtd2iBaZuMg+DYTFttTTipVZCrZI2Mlue0PVVK6tAmagEoKF6/tWdUv4kuassxAqXwIWbcrNBAIpoCAAtE4rHxV2uOE+1o/K4SGxT6iL9DgBJgA1O9aAEVktGopBVZf6iSkjXto7bkgaY+rkGDOZnVkyV9PLoHrVUFzWzOQCjJbNJumtI5kT6s5pNFkA8WUQ+j3sQbUk27shCAFpyzwN4exoCNoDfZdzMVNdJYQAv84VVUqHEJJlovir5/lIRW8NBgOGJzqtS2caA/B7sbUkA5I7BfNGrURc5XU5CSH8qQsZYd/1adoywCyDyyIDMLp/6kDwS1EhZF46Bey8FE1hyQYXUaMRYJkWrnz10LlCepGhbwpUoRBQsPG66Vq2Vf3wmhlyWkasYVRS7oFP4myXj/APS8VlFlEuF4idU0UI1qcGoG8dw0jVWT6WKiCsJzhFCCOmCYS5aVkS7H6bkv1xOLHeZCyGEuFQv6STyM4ISw4w/1L3n+jGS+Jrm5H0X03G6d8k4OIXU+6cmiLU8UO2qq6Zdw84aniiVcPsHtRfvZRYNEq5TX2SKHjDdwO37ICUTZCMq4KhwXk87Em3TfxO/cQHFH5aioreKqZLAYEpjGag6nd0L3DAmfbWXuL3RUFwWo8SzA23y0wjjP8hgqnNQeYNnJZPBtwPRNlelK2UYlJao5aZkZfB8niEowmKNMCNCCBFYP5FO6R335CiCyG8jQghRpYhv4xNlBIUQk4Q5341fJCyD6JWCWrSAG7EJDWK+aBFokxd8ctu/De92L8D5h3J7Xk4cBJzNXwG+z/S0qegAeSW909OtPqPqiXynD7cOJLX0+Mv3cqxQzhqZck9YejqYZFwaJao6prK9Nl2QPvHl7r/Qf1v4WDPV1dD1UDxaNCo/z1LShJQASoOwpKJc+ZR5i4iBVg2GuEU5/T4UIYQQujAhYq4gWC6E8rCY3SKEEM0gNLPzjBhPT2g3WoQSFuARQoiAJGtWVbUPtayVHUEXH2vmDiweWVP3Ys3T5aRre/qhAJC3+DmQCqrWNPLL5uALurU/0VUYWKzuem3XlmCoNnnrtW7RvT7Jc6kgrxuEEHUiIIRXCBEAiAUUz8N1M2YseNg0I16AiBDCEhMik5SJhAjVrhHVhiKe6BRiAoARv0lRFsy4uM40byq3ZLhF4GnRLISo6g9xXkgRUTFLmIoQzW5HsEZZtqAubgbcJsUjhKmIJp8Q5ooVatZ6iYlk0P7s1gRIr4qtiyqWPt1xcwNmx8lde5Rgh00otE+ExXIhYuL4ZLBA0cJm3XFEnrhWCCFmiIpQiFCIlipFNApTOUZgYXhjo1BcmIqY9V0hAoRCKkwP5s2N0/H8FdeGlZ112UzMvq+zuthptJp4R1KoH4ISYtGjfn+fFy4o2/4FQLHxA2oSAJG9q2/D+d6eLTUfTUYFdQ/D99LPJ8uzzQBLj+uyH0BLXnSEsKd9C7uCoELH1UHHrvm9nf9L+EVg5ajJLVsN/EC7PoaT/SXaunq3hfvETGmiz/Su/ol2eJRCsuVd2XbxUKJm78BpivMj2cJl6w8QqJxmknkwnf/x0tI579eNbfoPE+rPCt+cwjUdtmx0Dd2T1PpMML6IJBn7M76IJBcntxp3rdods+U4oBWS2tKdQMH8ZccJBDN3ZrShnSlPfNF/6ZbYmq3fxrOtaP0M35sZu7/mehMnkZ8Hz3fYRTC2F0XzvzAu0+Cz+f1j9t9xK8aReXyM81b2OHoPPk1l3XDWifLOnIHR+2vvuB9v/RXbWzPUW6NHmrVTDlYNTanoe2r9oYvuPLLf3d749kH/f1Tn3dPmPVim3SVnGrc+DPyNRCL4wcEYbH38zdSsc23/klWp7zT6bNS7nWB7JTMtu2TKqhif0J35GzqtS97C+MXNANzXbaOelUw/dtfcuPbHFWOG164zcHw3t2nzDycAmtgAEOy5O3b7/StjXP3OmEnRaD/gUZyhg4XaDk8sDjt2AGrtUKDQ/baSTG+8fP2YGpcdfDeIA8En79Imb5wx9dygOlP90tm/2UYPJtVrmk4sitduopDg7Gpz4WPL3hw6/cMLe7kmmDUhn2TWj7MnEtTP7gfyZ9rPNBwd3h2vzCQLG69CDwM1j3WcZNrdlbm1cjf7l9sj/zIyXpTyuuldn4iR5XG0tqWLuk864r9+y1ug5Wv295qOsvhFbl99xARtpOoUtw5Ndzxb+TYOg4UrkijdrT6nywvayI0X7jjFJYL1wuabX3dtK6hnfwrQeP2NJZcnJa2DvWTmzgF3JqHwKeCvXVS6v/QihG7rw8mdvqpjFp6997Wl+/z/7zKn/IE/9Q48yhNd424/L8qYq5kTCORtT3n8fWYMRjnJddH/AIeKnxqbB9+FAAAAAElFTkSuQmCC"

_LOGO_TAG = (
    f'<img src="{LOGO_URI}" alt="MCBI" width="52" height="52">'
    if LOGO_URI else ""
)


def header_html(lang):
    return f"""
<header class="mcbi-header">
  {_LOGO_TAG}
  <div class="mcbi-brand">
    <span class="mcbi-title">MCBI EPR</span>
    <span class="mcbi-sub">{t(lang, "brand_sub")}</span>
  </div>
  <span class="mcbi-badge">{t(lang, "badge")}</span>
</header>
"""


def intro_html(title_key, text_key):
    def build(lang):
        return (
            f'<div class="mcbi-intro"><h2>{t(lang, title_key)}</h2>'
            f'<p>{t(lang, text_key)}</p></div>'
        )
    return build


def step_html(number, key):
    def build(lang):
        return (f'<h3 class="mcbi-step-title"><span>{number}</span>'
                f'{t(lang, key)}</h3>')
    return build


def plain_title_html(key):
    def build(lang):
        return f'<h3 class="mcbi-step-title">{t(lang, key)}</h3>'
    return build


def edit_header_html(lang):
    return (f'<h3 class="mcbi-step-title">{t(lang, "edit_title")}</h3>'
            f'<p class="mcbi-small">{t(lang, "edit_note")}</p>')


def footer_md(lang):
    return f"---\n**MCBI EPR Pilot — N-064** · {t(lang, 'footer')}"


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
#mcbi-lang { min-width: 190px; }
#mcbi-footer { opacity: 0.8; font-size: 0.9em; }
"""




CSS += """
.mcbi-account { background: #FFFFFF; border: 1px solid #E2DED4 !important;
  border-radius: 14px !important; padding: 10px 16px !important;
  margin: 4px 0 10px; align-items: end; }
.mcbi-account p { margin: 0; }
"""


# ---------- Language-aware components ----------
# Every component whose text depends on the language is created with mk().
# mk() fills in the starting text and remembers how to re-translate the
# component, so switching language needs no extra code per component.

L0 = DEFAULT_LANG
TRANSLATABLE = []   # (component, {property: text key or function(lang)})


def mk(component_class, spec, **kwargs):
    initial = {
        prop: (source(L0) if callable(source) else t(L0, source))
        for prop, source in spec.items()
    }
    component = component_class(**initial, **kwargs)
    TRANSLATABLE.append((component, spec))
    return component


def translation_updates(lang):
    updates = []
    for _component, spec in TRANSLATABLE:
        updates.append(gr.update(**{
            prop: (source(lang) if callable(source) else t(lang, source))
            for prop, source in spec.items()
        }))
    return updates


def bulk_intro_text(lang):
    return t(lang, "bulk_intro", max=MAX_CSV_ROWS)


with gr.Blocks(title="MCBI EPR Portal") as demo:
    session = gr.State(None)      # the signed-in organization (per browser tab)

    with gr.Row(equal_height=True):
        mk(gr.HTML, {"value": header_html})
        lang = gr.Radio(
            list(LANGUAGES), value=L0, show_label=False, container=False,
            elem_id="mcbi-lang", scale=0, min_width=200
        )

    # ---------- Sign in once; every tab below uses it ----------
    with gr.Column(elem_classes="mcbi-account") as login_box:
        mk(gr.Markdown, {"value": "signin_hint"})
        with gr.Row():
            acct_email = mk(gr.Textbox, {"label": "acct_email"})
            acct_password = mk(gr.Textbox, {"label": "acct_password"},
                               type="password")
            signin_button = mk(gr.Button, {"value": "btn_signin"},
                               variant="primary", scale=0, min_width=140)
    with gr.Row(visible=False, elem_classes="mcbi-account") as account_bar:
        account_md = gr.Markdown("")
        signout_button = mk(gr.Button, {"value": "btn_signout"},
                            variant="secondary", scale=0, min_width=140)

    with gr.Tabs():

        # ---------- 1. Public lookup (default tab; QR links open here) ----------
        with mk(gr.Tab, {"label": "tab_find"}, id="find"):
            mk(gr.HTML, {"value": intro_html("find_title", "find_intro")})
            with gr.Row(equal_height=True):
                lookup_id = mk(
                    gr.Textbox, {"label": "battery_id"},
                    placeholder="MCBI-8B675499...", scale=4
                )
                lookup_button = mk(
                    gr.Button, {"value": "btn_find"}, variant="primary",
                    scale=1, size="lg"
                )
            lookup_card = gr.HTML(lookup_empty(L0))
            lookup_link = mk(
                gr.Textbox,
                {"label": "public_link", "info": "public_link_info"},
                interactive=False, buttons=["copy"], visible=False
            )

            for trigger in (lookup_button.click, lookup_id.submit):
                trigger(
                    fn=find_battery,
                    inputs=[lookup_id, lang],
                    outputs=[lookup_card, lookup_link]
                ).then(
                    fn=None,
                    inputs=[lookup_id, lookup_link],
                    js=SYNC_URL_JS
                )

        # ---------- 2. Registration (needs sign-in) ----------
        with mk(gr.Tab, {"label": "tab_register"}, id="register"):
            mk(gr.HTML, {"value": intro_html("reg_title", "reg_intro")})

            with gr.Column(elem_classes="mcbi-card"):
                mk(gr.HTML, {"value": step_html(1, "step1")})
                mk(gr.Markdown, {"value": "company_note"})
                with gr.Row():
                    category = mk(
                        gr.Dropdown,
                        {"choices": category_choices, "label": "category"},
                        value=None
                    )
                with gr.Row():
                    chemistry = mk(
                        gr.Dropdown,
                        {"choices": chemistry_choices, "label": "chemistry"},
                        value=None
                    )
                    weight = mk(gr.Number, {"label": "weight_kg"},
                                value=None)
                with gr.Row():
                    capacity = mk(gr.Number, {"label": "capacity"},
                                  value=None)
                    capacity_unit = mk(
                        gr.Radio, {"label": "unit"},
                        choices=list(CAPACITY_UNITS), value="Wh"
                    )
                    voltage = mk(
                        gr.Number,
                        {"label": "voltage", "info": "voltage_info"},
                        value=None
                    )

            with gr.Column(elem_classes="mcbi-card"):
                mk(gr.HTML, {"value": step_html(2, "step2")})
                granularity = mk(
                    gr.Radio,
                    {"choices": level_choices, "label": "reg_level"},
                    value=None
                )
                level_hint_box = gr.Markdown(level_hint(L0, None))
                with gr.Row():
                    model_id = gr.Textbox(
                        label=id_label(L0, "model_id", None), visible=False
                    )
                    batch_number = gr.Textbox(
                        label=id_label(L0, "batch_number", None), visible=False
                    )
                    serial_number = gr.Textbox(
                        label=id_label(L0, "serial_number", None), visible=False
                    )

                granularity.change(
                    fn=id_field_updates,
                    inputs=[granularity, lang],
                    outputs=[model_id, batch_number, serial_number,
                             level_hint_box]
                )

            with gr.Column(elem_classes="mcbi-card"):
                mk(gr.HTML, {"value": step_html(3, "step3")})
                with gr.Row():
                    country = mk(
                        gr.Textbox,
                        {"label": "country", "placeholder": "country_ph"}
                    )
                    manufacture_date = mk(
                        gr.Textbox,
                        {"label": "mfg_date", "info": "mfg_date_info"},
                        placeholder="2026-09"
                    )
                    status = mk(
                        gr.Dropdown,
                        {"choices": status_choices, "label": "lifecycle_status"},
                        value="original"
                    )
                with mk(gr.Accordion, {"label": "passport_acc"}, open=False):
                    with gr.Row():
                        carbon = mk(gr.Number, {"label": "carbon"},
                                    value=None)
                        recycled = mk(gr.Number, {"label": "recycled"},
                                      value=None)
                        soh = mk(gr.Number, {"label": "soh"},
                                 value=None)
                    address = mk(gr.Textbox, {"label": "mfr_address"})

            with gr.Column(elem_classes="mcbi-card"):
                mk(gr.HTML, {"value": step_html(4, "step4")})
                with gr.Row():
                    register_button = mk(
                        gr.Button, {"value": "btn_register"},
                        variant="primary", size="lg", scale=3
                    )
                    clear_button = mk(
                        gr.Button, {"value": "btn_clear"},
                        variant="secondary", size="lg", scale=1
                    )

            last_result = gr.State({})
            with gr.Column(visible=False) as result_group:
                result_card = gr.HTML()
                with gr.Row():
                    battery_id_output = mk(
                        gr.Textbox, {"label": "battery_id"},
                        interactive=False, buttons=["copy"]
                    )
                    register_link = mk(
                        gr.Textbox, {"label": "public_link"},
                        interactive=False, buttons=["copy"]
                    )
                with gr.Row():
                    qr_download = mk(
                        gr.DownloadButton, {"label": "btn_download_qr"},
                        variant="primary", size="lg"
                    )
                    register_another = mk(
                        gr.Button, {"value": "btn_register_another"},
                        variant="secondary", size="lg"
                    )

            battery_fields = [
                category, chemistry, weight, capacity, capacity_unit, voltage,
                granularity, model_id, batch_number, serial_number,
                country, manufacture_date, status, carbon, recycled, soh,
                address
            ]
            result_outputs = [
                result_group, result_card, battery_id_output, register_link,
                qr_download, last_result
            ]

            register_button.click(
                fn=register_battery,
                inputs=[session] + battery_fields + [lang],
                outputs=result_outputs
            ).success(
                # Clear the battery fields after a successful registration so
                # the same battery is not registered twice by accident.
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

            # ----- many batteries at once -----
            with mk(gr.Accordion, {"label": "bulk_title"}, open=False):
                mk(gr.Markdown, {"value": bulk_intro_text})
                template_button = mk(
                    gr.Button, {"value": "btn_template"}, variant="secondary"
                )
                template_file = mk(
                    gr.File, {"label": "file_word"}, interactive=False
                )
                bulk_input = mk(
                    gr.File, {"label": "bulk_file"},
                    file_types=[".csv"], type="filepath"
                )
                bulk_button = mk(
                    gr.Button, {"value": "btn_bulk"}, variant="primary"
                )
                bulk_result = mk(
                    gr.Textbox, {"label": "bulk_result"},
                    lines=6, interactive=False
                )
                bulk_zip = mk(
                    gr.File, {"label": "bulk_zip"}, interactive=False
                )
                export_mine_button = mk(
                    gr.Button, {"value": "btn_export_mine"},
                    variant="secondary"
                )
                export_mine_file = mk(
                    gr.File, {"label": "file_word"}, interactive=False
                )

                template_button.click(
                    fn=csv_template, inputs=lang, outputs=template_file
                )
                bulk_button.click(
                    fn=bulk_register,
                    inputs=[session, bulk_input, lang],
                    outputs=[bulk_result, bulk_zip]
                )
                export_mine_button.click(
                    fn=export_mine,
                    inputs=[session, lang],
                    outputs=export_mine_file
                )

        # ---------- 3. EPR market report (needs sign-in) ----------
        with mk(gr.Tab, {"label": "tab_epr"}, id="epr"):
            mk(gr.HTML, {"value": intro_html("epr_title", "epr_intro")})
            with gr.Column(elem_classes="mcbi-card"):
                with gr.Row():
                    epr_year = mk(
                        gr.Number, {"label": "epr_year"},
                        value=datetime.now(LOCAL_TZ).year, precision=0
                    )
                    epr_category = mk(
                        gr.Dropdown,
                        {"choices": category_choices, "label": "category"},
                        value=None
                    )
                with gr.Row():
                    epr_units = mk(
                        gr.Number, {"label": "epr_units"},
                        value=None, precision=0
                    )
                    epr_weight = mk(
                        gr.Number, {"label": "epr_weight"},
                        value=None
                    )
                with gr.Row():
                    save_report_button = mk(
                        gr.Button, {"value": "btn_save_report"},
                        variant="primary", size="lg", scale=3
                    )
                    show_reports_button = mk(
                        gr.Button, {"value": "btn_show_reports"},
                        variant="secondary", size="lg", scale=1
                    )
                epr_result = mk(
                    gr.Textbox, {"label": "result"}, interactive=False
                )
                epr_table = gr.Markdown("")

            save_report_button.click(
                fn=save_report,
                inputs=[session, epr_year, epr_category, epr_units,
                        epr_weight, lang],
                outputs=[epr_result, epr_table]
            )
            show_reports_button.click(
                fn=show_reports,
                inputs=[session, lang],
                outputs=epr_table
            )

        # ---------- Organization onboarding ----------
        with mk(gr.Tab, {"label": "tab_org"}, id="organization"):
            mk(gr.HTML, {"value": intro_html("org_title", "org_intro")})
            org_name_input = mk(gr.Textbox, {"label": "org_name"})
            org_email_input = mk(gr.Textbox, {"label": "org_email"})
            org_password_input = mk(
                gr.Textbox, {"label": "org_password_new"}, type="password"
            )
            with gr.Row():
                org_kind_input = mk(
                    gr.Dropdown,
                    {"choices": kind_choices, "label": "org_kind"},
                    value=None
                )
                org_country_input = mk(gr.Textbox, {"label": "org_country"})
            org_signup_result = mk(
                gr.Textbox, {"label": "result"}, interactive=False
            )
            org_submit = mk(gr.Button, {"value": "btn_org_submit"},
                            variant="primary")
            org_submit.click(
                fn=create_organization,
                inputs=[org_name_input, org_email_input, org_password_input,
                        org_kind_input, org_country_input, lang],
                outputs=org_signup_result
            )

        # ---------- 4. Admin ----------
        with mk(gr.Tab, {"label": "tab_admin"}, id="admin"):
            mk(gr.HTML, {"value": intro_html("admin_title", "admin_intro")})
            with gr.Column(elem_classes="mcbi-card"):
                admin_key = mk(
                    gr.Textbox, {"label": "admin_key"}, type="password"
                )

                recent_records = mk(
                    gr.Textbox, {"label": "recent_regs"},
                    lines=10, interactive=False
                )
                show_regs = mk(gr.Button, {"value": "btn_show_regs"})
                show_regs.click(
                    fn=admin_list_batteries,
                    inputs=[admin_key, lang],
                    outputs=recent_records
                )
                export_all_button = mk(
                    gr.Button, {"value": "btn_export_all"},
                    variant="secondary"
                )
                export_all_file = mk(
                    gr.File, {"label": "file_word"}, interactive=False
                )
                export_all_button.click(
                    fn=export_all,
                    inputs=[admin_key, lang],
                    outputs=export_all_file
                )

            with gr.Column(elem_classes="mcbi-card"):
                mk(gr.Markdown, {"value": "org_section"})
                organizations_result = mk(
                    gr.Textbox, {"label": "organizations"},
                    lines=8, interactive=False
                )
                show_orgs = mk(gr.Button, {"value": "btn_show_orgs"})
                show_orgs.click(
                    fn=list_organizations,
                    inputs=[admin_key, lang],
                    outputs=organizations_result
                )
                approve_org_id = mk(
                    gr.Number, {"label": "approve_id"}, precision=0
                )
                approve_org_result = mk(
                    gr.Textbox, {"label": "approve_result"}, interactive=False
                )
                approve_button = mk(
                    gr.Button, {"value": "btn_approve"}, variant="primary"
                )
                approve_button.click(
                    fn=approve_organization,
                    inputs=[approve_org_id, admin_key, lang],
                    outputs=approve_org_result
                )

            with gr.Column(elem_classes="mcbi-card"):
                market_button = mk(gr.Button, {"value": "btn_market"})
                market_table = gr.Markdown("")
                market_button.click(
                    fn=market_summary,
                    inputs=[admin_key, lang],
                    outputs=market_table
                )

            with gr.Column(elem_classes="mcbi-card"):
                admin_id = mk(gr.Textbox, {"label": "battery_id"})

                with gr.Row():
                    view_button = mk(gr.Button, {"value": "btn_private"})
                    history_button = mk(gr.Button, {"value": "btn_history"})
                admin_result = mk(
                    gr.Textbox, {"label": "private_record"},
                    lines=16, interactive=False
                )
                history_result = mk(
                    gr.Textbox, {"label": "history"},
                    lines=8, interactive=False
                )
                view_button.click(
                    fn=admin_find_battery,
                    inputs=[admin_id, admin_key, lang],
                    outputs=admin_result
                )
                history_button.click(
                    fn=admin_history,
                    inputs=[admin_id, admin_key, lang],
                    outputs=history_result
                )

            with gr.Column(elem_classes="mcbi-card"):
                mk(gr.HTML, {"value": plain_title_html("status_title")})
                with gr.Row():
                    new_status = mk(
                        gr.Dropdown,
                        {"choices": status_choices, "label": "new_status"}
                    )
                    status_reason = mk(gr.Textbox, {"label": "reason"})
                status_result = mk(
                    gr.Textbox, {"label": "result"}, interactive=False
                )
                update_status_button = mk(
                    gr.Button, {"value": "btn_update_status"}
                )
                update_status_button.click(
                    fn=change_status,
                    inputs=[admin_id, new_status, status_reason,
                            admin_key, lang],
                    outputs=status_result
                )

            with gr.Column(elem_classes="mcbi-card"):
                mk(gr.HTML, {"value": edit_header_html})
                with gr.Row():
                    edit_field = mk(
                        gr.Dropdown,
                        {"choices": field_choices, "label": "edit_field"}
                    )
                    edit_value = mk(gr.Textbox, {"label": "edit_value"})
                edit_reason = mk(
                    gr.Textbox,
                    {"label": "reason", "placeholder": "edit_reason_ph"}
                )
                edit_result = mk(
                    gr.Textbox, {"label": "result"}, interactive=False
                )
                save_edit_button = mk(gr.Button, {"value": "btn_save_edit"})
                save_edit_button.click(
                    fn=edit_battery,
                    inputs=[admin_id, edit_field, edit_value, edit_reason,
                            admin_key, lang],
                    outputs=edit_result
                )

    mk(gr.Markdown, {"value": footer_md}, elem_id="mcbi-footer")

    # ---------- Signing in and out ----------
    sign_in_outputs = [session, login_box, account_bar, account_md,
                       acct_password]
    for trigger in (signin_button.click, acct_password.submit):
        trigger(
            fn=sign_in,
            inputs=[acct_email, acct_password, lang],
            outputs=sign_in_outputs
        )
    signout_button.click(
        fn=sign_out,
        inputs=lang,
        outputs=[session, login_box, account_bar, account_md]
    )

    # ---------- Changing the language ----------
    # Besides the components registered with mk(), a few things depend on
    # what is currently on screen and are redrawn here: the level hint, the
    # three identification labels, the looked-up record, the result card and
    # the "signed in as" line.

    def switch_language(chosen, lookup_value, level, last, org):
        card, _link = find_battery(lookup_value, chosen)
        result_html = ""
        if last:
            result_html = private_card(
                last, make_qr(last["battery_id"]), chosen
            )
        return translation_updates(chosen) + [
            level_hint(chosen, level),
            gr.update(label=id_label(chosen, "model_id", level)),
            gr.update(label=id_label(chosen, "batch_number", level)),
            gr.update(label=id_label(chosen, "serial_number", level)),
            card,
            result_html,
            account_views(org, chosen)[2],
        ]

    lang.change(
        fn=switch_language,
        inputs=[lang, lookup_id, granularity, last_result, session],
        outputs=[component for component, _spec in TRANSLATABLE] + [
            level_hint_box, model_id, batch_number, serial_number,
            lookup_card, result_card, account_md
        ],
    ).then(fn=None, inputs=lang, js=LANG_URL_JS)

    demo.load(
        fn=load_battery_from_url,
        inputs=[],
        outputs=[lang, lookup_id, lookup_card, lookup_link]
    )
    # Gradio shows an untouched number box as 0 unless it is reset on load;
    # without this an empty optional field (state of health, carbon ...)
    # would be saved as 0.
    number_boxes = [weight, capacity, voltage, carbon, recycled, soh,
                    epr_units, epr_weight]
    demo.load(fn=lambda: (None,) * len(number_boxes), inputs=[],
              outputs=number_boxes)


port = int(os.getenv("PORT", "10000"))

# The portal page and the QR / JSON addresses run together in one server.
app = gr.mount_gradio_app(
    api, demo, path="/",
    ssr_mode=False, pwa=True, css=CSS, theme=THEME
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
