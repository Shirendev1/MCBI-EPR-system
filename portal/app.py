import base64
import hmac
import html
import io
import math
import hashlib
import secrets
import os
import re
import tempfile
import time
import uuid
from collections import defaultdict
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
        "tab_org": "Organization signup",
        "tab_register": "Register",
        "tab_admin": "Admin",
        "footer": "Mongolia Circular Battery Initiative · Pilot prototype",

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
        "public_note": "Only category, chemistry and status are public.",
        "qr_alt": "QR code",
        "life_1": "New · in use",
        "life_2": "Reuse / second life",
        "life_3": "Collection and recycling",
        "waste_title": "Do not dispose of with household waste",
        "waste_text": "Take used batteries to a collection point.",

        # private card (after registering)
        "success_title": "Battery registered successfully",
        "success_text": "Print the QR code and attach it to the battery.",
        "battery_id_caps": "BATTERY ID",
        "company": "Company",
        "serial": "Serial number",
        "model": "Model",
        "batch": "Batch",
        "weight_word": "Weight",
        "kg": "kg",
        "made": "Made",
        "level": "Level",
        "private_note": "Company, weight and serial number stay private. Anyone who scans the QR code sees only category, chemistry and status.",

        # organization signup
        "org_title": "Organization signup",
        "org_intro": "Register your organization below. Battery registration becomes available after an MCBI administrator approves it.",
        "org_name": "Organization name",
        "org_email": "Organization email",
        "org_password_new": "Password (12+ characters)",
        "result": "Result",
        "btn_org_submit": "Submit organization request",

        # register tab
        "reg_title": "Register a battery",
        "reg_intro": "Every record gets a unique ID, a QR code and a public link. All fields are required unless marked optional.",
        "step1": "Basic information",
        "step2": "Identification",
        "step3": "Manufacturing",
        "step4": "Confirm",
        "company_note": "The company is filled in automatically from your organization.",
        "category": "Category",
        "chemistry": "Chemistry",
        "weight_kg": "Weight, kg",
        "capacity": "Capacity",
        "unit": "Unit",
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
        "org_email_login": "Organization email",
        "org_password_login": "Organization password",
        "btn_register": "Register battery",
        "btn_clear": "Clear",
        "btn_download_qr": "Download QR label (PNG)",
        "btn_register_another": "Register another battery",

        # admin tab
        "admin_title": "Administration",
        "admin_intro": "Do not share your key or leave it on a shared computer.",
        "admin_key": "Admin key",
        "recent_regs": "Recent registrations",
        "btn_show_regs": "Show registrations",
        "org_section": "### Approve organization requests",
        "organizations": "Organizations",
        "btn_show_orgs": "Show organizations",
        "approve_id": "Organization ID to approve",
        "approve_result": "Approval result",
        "btn_approve": "Approve organization",
        "btn_private": "Private record",
        "btn_history": "History",
        "private_record": "Private record",
        "history": "Registration and status history",
        "status_title": "Change status",
        "new_status": "New status",
        "reason": "Reason",
        "btn_update_status": "Update status",
        "edit_title": "Correct a record",
        "edit_note": "Fix a mistyped field. The old value is kept in the history.",
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
        "msg_no_orgs": "No organizations found.",
        "org_approved_word": "Approved",
        "org_pending_word": "Pending",
        "err_org_id": "Organization ID must be a number.",
        "err_org_missing": "Organization not found.",
        "msg_org_approved": "{name} has been approved.",
        "err_required": "{label} is required.",
        "err_positive": "{label} must be a positive number.",
        "err_select_main": "Select a category, chemistry and registration level.",
        "err_select_status": "Select a lifecycle status and capacity unit.",
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
        "rec_labels": (
            "Battery ID", "Company", "Category", "Chemistry", "Weight (kg)",
            "Capacity", "Capacity unit", "Registration level", "Model / SKU",
            "Batch number", "Serial number", "Manufacturing country",
            "Manufacturing date", "Lifecycle status", "Registered",
        ),
        "ev_registered": "registered",
        "ev_status_changed": "status changed",
        "ev_edited": "edited",
    },
    "mn": {
        "brand_sub": "Монголын тойрог батарейн санаачилга · Батарей бүртгэлийн портал",
        "badge": "ТУРШИЛТ · N-064",
        "tab_find": "Хайх",
        "tab_org": "Байгууллага бүртгүүлэх",
        "tab_register": "Бүртгэх",
        "tab_admin": "Админ",
        "footer": "Монголын тойрог батарейн санаачилга · Туршилтын хувилбар",

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
        "public_note": "Нийтэд зөвхөн ангилал, химийн төрөл, төлөв харагдана.",
        "qr_alt": "QR код",
        "life_1": "Шинэ · ашиглалтад",
        "life_2": "Дахин ашиглалт / хоёр дахь амьдрал",
        "life_3": "Цуглуулалт ба дахин боловсруулалт",
        "waste_title": "Энгийн хогтой хамт хаяж болохгүй",
        "waste_text": "Ашиглалтаас гарсан батарейг цуглуулах цэгт хүлээлгэн өгнө.",

        "success_title": "Батарей амжилттай бүртгэгдлээ",
        "success_text": "QR кодыг хэвлээд батарейн их бие дээр наана уу.",
        "battery_id_caps": "БАТАРЕЙН ID",
        "company": "Компани",
        "serial": "Серийн дугаар",
        "model": "Загвар",
        "batch": "Багц",
        "weight_word": "Жин",
        "kg": "кг",
        "made": "Үйлдвэрлэсэн",
        "level": "Түвшин",
        "private_note": "Компани, жин, серийн дугаар нууц. QR уншуулсан хүн зөвхөн ангилал, химийн төрөл, төлөвийг харна.",

        "org_title": "Байгууллагын бүртгэл",
        "org_intro": "Байгууллагаа доор бүртгүүлнэ үү. MCBI админ зөвшөөрсний дараа батарей бүртгэх боломжтой болно.",
        "org_name": "Байгууллагын нэр",
        "org_email": "Байгууллагын имэйл",
        "org_password_new": "Нууц үг (12+ тэмдэгт)",
        "result": "Үр дүн",
        "btn_org_submit": "Байгууллага бүртгүүлэх",

        "reg_title": "Батарей бүртгэх",
        "reg_intro": "Бүртгэл бүр өвөрмөц ID, QR код, нийтийн холбоос авна. «Сонголтоор» гэснээс бусад бүх талбар заавал.",
        "step1": "Үндсэн мэдээлэл",
        "step2": "Таних мэдээлэл",
        "step3": "Үйлдвэрлэл",
        "step4": "Баталгаажуулах",
        "company_note": "Компани нь таны байгууллагын нэрээр автоматаар бүртгэгдэнэ.",
        "category": "Ангилал",
        "chemistry": "Химийн төрөл",
        "weight_kg": "Жин, кг",
        "capacity": "Багтаамж",
        "unit": "Нэгж",
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
        "org_email_login": "Байгууллагын имэйл",
        "org_password_login": "Байгууллагын нууц үг",
        "btn_register": "Батарей бүртгэх",
        "btn_clear": "Цэвэрлэх",
        "btn_download_qr": "QR шошго татах (PNG)",
        "btn_register_another": "Дараагийн батарей бүртгэх",

        "admin_title": "Админ",
        "admin_intro": "Түлхүүрээ бусадтай хуваалцах, нийтийн компьютер дээр үлдээхгүй байгаарай.",
        "admin_key": "Админ түлхүүр",
        "recent_regs": "Сүүлийн бүртгэлүүд",
        "btn_show_regs": "Бүртгэлүүдийг харах",
        "org_section": "### Байгууллагын хүсэлт зөвшөөрөх",
        "organizations": "Байгууллагууд",
        "btn_show_orgs": "Байгууллагуудыг харах",
        "approve_id": "Зөвшөөрөх байгууллагын ID",
        "approve_result": "Зөвшөөрлийн үр дүн",
        "btn_approve": "Байгууллага зөвшөөрөх",
        "btn_private": "Дэлгэрэнгүй",
        "btn_history": "Түүх",
        "private_record": "Нууц мэдээлэл",
        "history": "Бүртгэл ба төлөвийн түүх",
        "status_title": "Төлөв өөрчлөх",
        "new_status": "Шинэ төлөв",
        "reason": "Шалтгаан",
        "btn_update_status": "Төлөв шинэчлэх",
        "edit_title": "Бүртгэл засах",
        "edit_note": "Алдаатай бичсэн талбарыг засна. Хуучин утга түүхэнд хадгалагдана.",
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
        "msg_no_orgs": "Байгууллага алга.",
        "org_approved_word": "Зөвшөөрсөн",
        "org_pending_word": "Хүлээгдэж буй",
        "err_org_id": "Байгууллагын ID тоо байх ёстой.",
        "err_org_missing": "Байгууллага олдсонгүй.",
        "msg_org_approved": "{name} байгууллагыг зөвшөөрлөө.",
        "err_required": "{label}: заавал бөглөнө.",
        "err_positive": "{label}: 0-ээс их тоо оруулна уу.",
        "err_select_main": "Ангилал, химийн төрөл, бүртгэлийн түвшнээ сонгоно уу.",
        "err_select_status": "Төлөв болон багтаамжийн нэгжээ сонгоно уу.",
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
        "rec_labels": (
            "Батарейн ID", "Компани", "Ангилал", "Химийн төрөл", "Жин (кг)",
            "Багтаамж", "Багтаамжийн нэгж", "Бүртгэлийн түвшин", "Загвар / SKU",
            "Багцын дугаар", "Серийн дугаар", "Үйлдвэрлэсэн улс",
            "Үйлдвэрлэсэн огноо", "Амьдралын мөчлөг", "Бүртгэсэн",
        ),
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
# Fields an admin may correct after registration: column -> label per language
FIELD_LABELS = {
    "company": {"en": "Company", "mn": "Компани"},
    "category": {"en": "Category", "mn": "Ангилал"},
    "chemistry": {"en": "Chemistry", "mn": "Химийн төрөл"},
    "weight": {"en": "Weight (kg)", "mn": "Жин (кг)"},
    "capacity": {"en": "Capacity", "mn": "Багтаамж"},
    "capacity_unit": {"en": "Capacity unit", "mn": "Багтаамжийн нэгж"},
    "granularity": {"en": "Registration level", "mn": "Бүртгэлийн түвшин"},
    "model_id": {"en": "Model / SKU", "mn": "Загвар / SKU"},
    "batch_number": {"en": "Batch number", "mn": "Багцын дугаар"},
    "serial_number": {"en": "Serial number", "mn": "Серийн дугаар"},
    "country": {"en": "Country of manufacture", "mn": "Үйлдвэрлэсэн улс"},
    "manufacture_date": {"en": "Manufacturing date", "mn": "Үйлдвэрлэсэн огноо"},
}
EDITABLE_COLUMNS = tuple(FIELD_LABELS)
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


# ---------- Login attempt limiting (kept in memory; resets on restart) ----------

FAILED_LOGINS = defaultdict(list)
MAX_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60


def check_login_limit(key, lang):
    """Block a key (email or admin) after too many recent failures."""
    now = time.time()
    FAILED_LOGINS[key] = [t_ for t_ in FAILED_LOGINS[key] if now - t_ < LOCK_SECONDS]
    if len(FAILED_LOGINS[key]) >= MAX_ATTEMPTS:
        raise gr.Error(t(lang, "err_too_many"))


def require_admin_key(key, lang):
    check_login_limit("__admin__", lang)
    expected = os.getenv("REGISTRATION_KEY")
    if not expected or not hmac.compare_digest((key or "").encode("utf-8"), expected.encode("utf-8")):
        FAILED_LOGINS["__admin__"].append(time.time())
        raise gr.Error(t(lang, "err_admin_key"))


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


def required_text(value, label, lang):
    value = (value or "").strip()
    if not value:
        raise gr.Error(t(lang, "err_required", label=label))
    return value


def positive_number(value, label, lang):
    if (
        value is None
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise gr.Error(t(lang, "err_positive", label=label))
    return value


def create_organization(name, email, password, lang):
    name = required_text(name, t(lang, "org_name"), lang)
    email = required_text(email, t(lang, "org_email"), lang).lower()
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
                cur.execute("INSERT INTO organizations (name,email,password_hash) VALUES (%s,%s,%s)",
                            (name, email, hash_password(password)))
    return t(lang, "msg_org_submitted")


def authenticate_organization(email, password, lang):
    email = (email or "").strip().lower()
    check_login_limit(email, lang)
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,name,password_hash,approved FROM organizations WHERE email=%s", (email,))
            record = cur.fetchone()
    if not record or not password_matches(password or "", record[2]):
        FAILED_LOGINS[email].append(time.time())
        raise gr.Error(t(lang, "err_login"))
    FAILED_LOGINS.pop(email, None)
    if not record[3]:
        raise gr.Error(t(lang, "err_not_approved"))
    return record[0], record[1]


def list_organizations(admin_key, lang):
    require_admin_key(admin_key, lang)
    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,name,email,approved FROM organizations ORDER BY id DESC LIMIT 100")
            rows = cur.fetchall()
    approved_word = t(lang, "org_approved_word")
    pending_word = t(lang, "org_pending_word")
    return "\n".join(
        f"ID {i} | {name} | {email} | {approved_word if approved else pending_word}"
        for i, name, email, approved in rows
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


# ---------- HTML building blocks (all user text is escaped) ----------

def esc(value):
    if value is None or value == "":
        return "—"
    return html.escape(str(value))


def fmt_number(value):
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
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


def public_card(record, lang):
    battery_id, category, chemistry, status, registered_at = record
    qr = image_data_uri(make_qr(battery_id))
    registered = local_time(registered_at)
    return f"""
<div class="mcbi-passport">
  <div class="mcbi-passport-dark">
    <span class="mcbi-eyebrow">{t(lang, "pp_eyebrow")}</span>
    <span class="mcbi-big">{esc(chemistry_name(lang, chemistry))} {t(lang, "battery_word")}</span>
    <span class="mcbi-muted-light">{esc(category_name(lang, category))}</span>
    <span class="mcbi-id">{esc(battery_id)}</span>
    <img class="mcbi-qr" src="{qr}" alt="{t(lang, "qr_alt")}">
  </div>
  <div class="mcbi-passport-body">
    <div class="mcbi-row">
      <span class="mcbi-label">{t(lang, "lifecycle")}</span>
      <span class="mcbi-chip">{esc(status_name(lang, status))}</span>
    </div>
    {lifecycle_html(status, lang)}
    <span class="mcbi-small">{t(lang, "registered")}: {esc(registered)}</span>
    {waste_note(lang)}
    <p class="mcbi-small">{t(lang, "public_note")}</p>
  </div>
</div>
"""


def private_card(values, qr_image, lang):
    qr = image_data_uri(qr_image)
    rows = (
        (t(lang, "company"), values["company"]),
        (t(lang, "serial"), values["serial_number"]),
        (t(lang, "model"), values["model_id"]),
        (t(lang, "batch"), values["batch_number"]),
        (t(lang, "weight_word"), f"{fmt_number(values['weight'])} {t(lang, 'kg')}"),
        (t(lang, "made"), f"{values['country']} · {values['manufacture_date']}"),
        (t(lang, "level"), level_name(lang, values["granularity"])),
        (t(lang, "registered"), values["registered"]),
    )
    cells = "".join(
        f'<div><dt>{label}</dt><dd>{esc(value)}</dd></div>'
        for label, value in rows
    )
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
    <dl class="mcbi-grid">{cells}</dl>
    <p class="mcbi-small">{t(lang, "private_note")}</p>
  </div>
</div>
"""


def message_card(text):
    return f'<div class="mcbi-empty">{text}</div>'


def lookup_empty(lang):
    return message_card(t(lang, "lookup_empty"))


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
                    CREATE TABLE IF NOT EXISTS organizations (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        approved BOOLEAN NOT NULL DEFAULT FALSE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("ALTER TABLE batteries ADD COLUMN IF NOT EXISTS organization_id BIGINT REFERENCES organizations(id)")

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
    organization_email,
    organization_password,
    lang
):
    org_id, org_name = authenticate_organization(organization_email, organization_password, lang)

    company = org_name  # Verified company identity; never trust a free-text company name
    if (
        category not in CATEGORIES
        or chemistry not in CHEMISTRIES
        or granularity not in LEVELS
    ):
        raise gr.Error(t(lang, "err_select_main"))

    if status not in STATUSES or capacity_unit not in CAPACITY_UNITS:
        raise gr.Error(t(lang, "err_select_status"))

    weight = positive_number(weight, t(lang, "weight_kg"), lang)
    capacity = positive_number(capacity, t(lang, "capacity"), lang)

    country = required_text(country, t(lang, "country"), lang)
    manufacture_date = required_text(manufacture_date, t(lang, "mfg_date"), lang)
    model_id = (model_id or "").strip()
    batch_number = (batch_number or "").strip()
    serial_number = (serial_number or "").strip()

    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", manufacture_date):
        raise gr.Error(t(lang, "err_date"))

    # Drop identification values that this level does not use
    # (e.g. no serial number on an SKU registration).
    level_fields = LEVEL_FIELDS[granularity]
    if "batch_number" not in level_fields:
        batch_number = ""
    if "serial_number" not in level_fields:
        serial_number = ""

    if granularity == "SKU" and not model_id:
        raise gr.Error(t(lang, "err_need_model"))

    if granularity == "Batch" and not batch_number:
        raise gr.Error(t(lang, "err_need_batch"))

    if granularity == "Unit" and not serial_number:
        raise gr.Error(t(lang, "err_need_serial"))

    battery_id = "MCBI-" + uuid.uuid4().hex[:16].upper()

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO batteries (
                        id, company, category, chemistry, weight,
                        capacity, capacity_unit, granularity, model_id,
                        batch_number, serial_number, country,
                        manufacture_date, status, organization_id
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    battery_id, company, category, chemistry,
                    weight, capacity, capacity_unit, granularity,
                    model_id, batch_number, serial_number, country,
                    manufacture_date, status, org_id
                ))

                cur.execute("""
                    INSERT INTO battery_events (
                        battery_id, event_type, new_value
                    )
                    VALUES (%s, 'registered', %s)
                """, (battery_id, status))

    qr = make_qr(battery_id)
    values = {
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
    }

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


def find_battery(battery_id, lang):
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return lookup_empty(lang), gr.update(value="", visible=False)

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
            message_card(t(lang, "lookup_notfound")),
            gr.update(value="", visible=False),
        )

    return public_card(record, lang), gr.update(
        value=record_link(record[0]), visible=True
    )


def admin_find_battery(battery_id, admin_key, lang):
    require_admin_key(admin_key, lang)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return t(lang, "err_enter_id")

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
        return t(lang, "err_battery_missing")

    values = list(record)
    values[-1] = local_time(values[-1])

    return "\n".join(
        f"{label}: {value if value is not None else '—'}"
        for label, value in zip(t(lang, "rec_labels"), values)
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


def admin_history(battery_id, admin_key, lang):
    require_admin_key(admin_key, lang)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        return t(lang, "err_enter_id")

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


def edit_battery(battery_id, column, new_value, reason, admin_key, lang):
    require_admin_key(admin_key, lang)
    battery_id = (battery_id or "").strip().upper()

    if not battery_id:
        raise gr.Error(t(lang, "err_enter_id"))
    if column not in EDITABLE_COLUMNS:
        raise gr.Error(t(lang, "err_select_field"))

    label = field_label(lang, column)
    reason = required_text(reason, t(lang, "reason"), lang)
    new_value = (new_value or "").strip()

    if column in ("company", "country"):
        new_value = required_text(new_value, label, lang)
    elif column in ENUM_FIELDS and new_value not in ENUM_FIELDS[column]:
        raise gr.Error(t(lang, "err_allowed", field=label,
                         values=", ".join(ENUM_FIELDS[column])))
    elif column in ("weight", "capacity"):
        try:
            number = float(new_value.replace(",", "."))
        except ValueError:
            raise gr.Error(t(lang, "err_number", field=label))
        new_value = positive_number(number, label, lang)
    elif column == "manufacture_date" and not re.fullmatch(
        r"\d{4}-(0[1-9]|1[0-2])", new_value
    ):
        raise gr.Error(t(lang, "err_date"))

    with closing(psycopg2.connect(DATABASE_URL)) as conn:
        with conn:
            with conn.cursor() as cur:
                # column comes from the fixed EDITABLE_COLUMNS whitelist
                cur.execute(
                    f"SELECT {column} FROM batteries WHERE id = %s FOR UPDATE",
                    (battery_id,)
                )
                row = cur.fetchone()
                if row is None:
                    raise gr.Error(t(lang, "err_battery_missing"))
                old_value = row[0]

                if str(old_value) == str(new_value):
                    return t(lang, "msg_no_change")

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

    return t(lang, "msg_edited", column=column, old=old_value, new=new_value)


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

# The MCBI logo, embedded in the page. Leave empty to show no logo.
LOGO_URI = "data:image/png;base64,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"

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


with gr.Blocks(title="MCBI EPR Portal") as demo:
    with gr.Row(equal_height=True):
        mk(gr.HTML, {"value": header_html})
        lang = gr.Radio(
            list(LANGUAGES), value=L0, show_label=False, container=False,
            elem_id="mcbi-lang", scale=0, min_width=200
        )

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

        # ---------- Organization onboarding ----------
        with mk(gr.Tab, {"label": "tab_org"}, id="organization"):
            mk(gr.HTML, {"value": intro_html("org_title", "org_intro")})
            org_name_input = mk(gr.Textbox, {"label": "org_name"})
            org_email_input = mk(gr.Textbox, {"label": "org_email"})
            org_password_input = mk(
                gr.Textbox, {"label": "org_password_new"}, type="password"
            )
            org_signup_result = mk(
                gr.Textbox, {"label": "result"}, interactive=False
            )
            org_submit = mk(gr.Button, {"value": "btn_org_submit"},
                            variant="primary")
            org_submit.click(
                fn=create_organization,
                inputs=[org_name_input, org_email_input,
                        org_password_input, lang],
                outputs=org_signup_result
            )

        # ---------- 2. Registration (needs an approved organization login) ----------
        with mk(gr.Tab, {"label": "tab_register"}, id="register"):
            mk(gr.HTML, {"value": intro_html("reg_title", "reg_intro")})

            with gr.Column(elem_classes="mcbi-card"):
                mk(gr.HTML, {"value": step_html(1, "step1")})
                # The company name is taken from the logged-in organization,
                # so there is no company field to fill in.
                company = gr.State("")
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
                                value=None, minimum=0)
                    capacity = mk(gr.Number, {"label": "capacity"},
                                  value=None, minimum=0)
                    capacity_unit = mk(
                        gr.Radio, {"label": "unit"},
                        choices=list(CAPACITY_UNITS), value="Wh"
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

            with gr.Column(elem_classes="mcbi-card"):
                mk(gr.HTML, {"value": step_html(4, "step4")})
                organization_email = mk(
                    gr.Textbox, {"label": "org_email_login"}
                )
                organization_password = mk(
                    gr.Textbox, {"label": "org_password_login"},
                    type="password"
                )
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
                category, chemistry, weight, capacity, capacity_unit,
                granularity, model_id, batch_number, serial_number,
                country, manufacture_date, status
            ]
            result_outputs = [
                result_group, result_card, battery_id_output, register_link,
                qr_download, last_result
            ]

            register_button.click(
                fn=register_battery,
                inputs=[
                    company, category, chemistry, weight, capacity,
                    capacity_unit, granularity, model_id, batch_number,
                    serial_number, country, manufacture_date, status,
                    organization_email, organization_password, lang
                ],
                outputs=result_outputs
            ).success(
                # Clear the battery fields after a successful registration so
                # the same battery is not registered twice by accident.
                # The organization email and password stay filled.
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
                admin_id = mk(gr.Textbox, {"label": "battery_id"})

                with gr.Row():
                    view_button = mk(gr.Button, {"value": "btn_private"})
                    history_button = mk(gr.Button, {"value": "btn_history"})
                admin_result = mk(
                    gr.Textbox, {"label": "private_record"},
                    lines=14, interactive=False
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

    # ---------- Changing the language ----------
    # Besides the components registered with mk(), four things depend on
    # what is currently on screen and are redrawn here: the level hint, the
    # three identification labels, the looked-up record and the result card.

    def switch_language(chosen, lookup_value, level, last):
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
        ]

    lang.change(
        fn=switch_language,
        inputs=[lang, lookup_id, granularity, last_result],
        outputs=[component for component, _spec in TRANSLATABLE] + [
            level_hint_box, model_id, batch_number, serial_number,
            lookup_card, result_card
        ],
    ).then(fn=None, inputs=lang, js=LANG_URL_JS)

    demo.load(
        fn=load_battery_from_url,
        inputs=[],
        outputs=[lang, lookup_id, lookup_card, lookup_link]
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
