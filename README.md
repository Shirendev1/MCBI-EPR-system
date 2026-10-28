# MCBI EPR Pilot Portal
### Монголын батарейн EPR туршилтын портал

**Battery registration, QR identification and lifecycle tracking for Mongolia's Extended Producer Responsibility (EPR) pilot.**
**Монголд үйлдвэрлэгчийн өргөтгөсөн хариуцлагын (EPR) тогтолцоог турших зорилгоор батарей бүртгэх, QR кодоор таних, амьдралын мөчлөгийг хянах систем.**

🔗 **Live portal / Ажиллаж буй портал:** https://passport.mcbis.org

Developed by the **Mongolia Circular Battery Initiative (MCBI)** as part of the COP17 project pipeline entry **N-064**.
**Монголын тойрог батарейн санаачилга (MCBI)**-ийн COP17 төслийн жагсаалтын **N-064** төслийн хүрээнд боловсруулав.

> **Status / Төлөв:** Working pilot prototype, currently tested with test data only. It does not collect payments.
> Ажиллаж буй туршилтын хувилбар. Одоогоор зөвхөн туршилтын өгөгдлөөр шалгаж байна. Төлбөр авдаггүй.

---

## Why this exists / Яагаад хэрэгтэй вэ

Mongolia has no system that tracks a battery from import to end of life. Used car batteries and other batteries often end up in informal recycling or in the environment. An EPR system makes producers and importers responsible for their products after use. That only works if every battery can be identified and followed.

This portal is a small, working first step. It registers each battery, gives it a unique ID and QR code, and records every change in its status. The data it produces is meant to inform Mongolia's battery EPR policy.

Монголд батарейг импортоос нь эхлээд хаягдал болох хүртэл хянадаг систем одоогоор байхгүй. Хуучин аккумулятор болон бусад батарей албан бус дахин боловсруулалтад орох эсвэл байгальд хаягдах нь элбэг. EPR тогтолцоо нь үйлдвэрлэгч, импортлогчийг бүтээгдэхүүнийхээ ашиглалтын дараах хариуцлагыг үүрэхийг шаарддаг. Үүний тулд батарей бүрийг таньж, хянах боломжтой байх ёстой.

Энэ портал нь тийм системийн жижиг боловч ажиллаж буй эхний алхам юм. Батарей бүрийг бүртгэж, өвөрмөц ID болон QR код олгож, төлвийн өөрчлөлт бүрийг хадгална. Эндээс гарах өгөгдөл нь Монголын батарейн EPR бодлогыг боловсруулахад ашиглагдана.

---

## What it does / Юу хийдэг вэ

The portal has five tabs. / Портал таван табтай.

| Tab / Таб | Who / Хэн | What / Юу хийх |
|---|---|---|
| 🔍 **Find / Хайх** | Anyone / Хэн ч | Look up a battery by ID or by scanning its QR code. Shows public information only. · ID эсвэл QR кодоор батарейг хайж, нийтийн мэдээллийг харна. |
| ➕ **Register / Бүртгэх** | Approved organizations / Зөвшөөрөгдсөн байгууллага | Register one battery, or many at once from a CSV file, and receive IDs and printable QR labels. Export your own records. · Нэг батарей эсвэл CSV файлаар олныг нэг дор бүртгэж, ID болон QR наалт авна. Өөрийн бүртгэлийг татаж авна. |
| 📊 **EPR report / EPR тайлан** | Approved organizations / Зөвшөөрөгдсөн байгууллага | Report units and weight placed on the market per year and category. · Жил, ангиллаар зах зээлд нийлүүлсэн тоо ширхэг, жинг тайлагнана. |
| 🏢 **Organization signup / Байгууллага бүртгүүлэх** | Companies, importers, recyclers / Компани, импортлогч, дахин боловсруулагч | Create an organization account. An administrator approves it before it can register batteries. · Байгууллагын бүртгэл үүсгэнэ. Админ зөвшөөрсний дараа батарей бүртгэх эрхтэй болно. |
| ⚙️ **Admin / Админ** | MCBI administrators (admin key) / MCBI админ (админ түлхүүр) | Approve organizations, list registrations, view private records and history, change lifecycle status, correct mistakes, export all data, market summary. · Байгууллага зөвшөөрөх, бүртгэл харах, түүх шалгах, төлөв өөрчлөх, алдаа засах, бүх өгөгдлийг татах, зах зээлийн нэгтгэл. |

### Key features / Гол боломжууд

- **Unique Battery ID and QR code.** Each QR code opens that battery's record directly on a phone.
  **Өвөрмөц ID ба QR код.** QR-ийг утсаар уншуулахад тухайн батарейн мэдээлэл шууд нээгдэнэ.
- **Full history, nothing overwritten.** Registrations, status changes and corrections are all logged with time and reason.
  **Бүрэн түүх.** Бүртгэл, төлвийн өөрчлөлт, засвар бүр цаг хугацаа, шалтгаантайгаа хадгалагдана. Юу ч устгагдахгүй.
- **Three access levels, as in the EU Battery Regulation.** Public: ID, category, chemistry, status, energy (kWh), carbon footprint, recycled content, registration date. Recyclers and repurposers (approved accounts) and the record's owner also see company, serial numbers and technical details. Administrators see everything.
  **ЕХ-ны журмын дагуу 3 түвшний хандалт.** Нийтэд: ID, ангилал, химийн төрөл, төлөв, эрчим хүч (kWh), нүүрстөрөгчийн ул мөр, дахин боловсруулсан материалын хувь, бүртгэсэн огноо. Дахин боловсруулагч, дахин ашиглагч (зөвшөөрөгдсөн бүртгэлтэй) болон бүртгэл эзэмшигч нь компани, серийн дугаар, техникийн мэдээллийг харна. Админ бүгдийг харна.
- **Duplicate protection.** An organization cannot register the same serial number twice.
  **Давхардлаас хамгаалалт.** Нэг байгууллага ижил серийн дугаарыг хоёр удаа бүртгэх боломжгүй.
- **Machine-readable data.** `/api/v1/batteries/<ID>` returns the record as JSON, grouped like the Battery Pass data model.
  **Машинд уншигдах өгөгдөл.** `/api/v1/batteries/<ID>` хаягаар бүртгэлийг JSON хэлбэрээр авна.
- **Bilingual interface** in Mongolian and English. Times are shown in Ulaanbaatar time.
  **Монгол, англи хоёр хэлтэй.** Цагийг Улаанбаатарын цагаар харуулна.
- **Installable on phones** as a web app (PWA).
  **Утсанд апп шиг суулгаж болно** (PWA).

---

## Data model / Өгөгдлийн бүтэц

Fields follow the categories used in the **EU Battery Regulation (EU) 2023/1542**, so the pilot data can later be aligned with a battery passport.
Талбаруудыг **ЕХ-ны Батарейн журам (EU) 2023/1542**-ийн ангиллын дагуу хийсэн тул цаашид батарейн паспорттой нийцүүлэх боломжтой.

| Field / Талбар | Values / Утга |
|---|---|
| Category / Ангилал | `SLI` (car starter), `EV`, `LMT`, `Stationary`, `Industrial`, `Consumer` |
| Chemistry / Химийн төрөл | `LFP`, `NMC`, `NCA`, `LCO`, `LMO`, `Lead-acid`, `Other` |
| Registration level / Бүртгэлийн түвшин | `SKU` (model), `Batch`, `Unit` (single battery) |
| Weight, capacity / Жин, багтаамж | kg; Wh or Ah |
| Identification / Таних мэдээлэл | Model/SKU, batch number, serial number |
| Manufacturing / Үйлдвэрлэл | Country, date (YYYY-MM) |
| Lifecycle status / Төлөв | `original`, `re-used`, `repurposed`, `remanufactured`, `waste` |

---

## Run it yourself / Өөрийн компьютер дээр ажиллуулах

Requirements: Python 3.10+ and PostgreSQL. / Шаардлага: Python 3.10+, PostgreSQL.

```bash
pip install -r portal/requirements.txt

export DATABASE_URL="postgresql://mcbi:mcbi_pass@localhost:5432/mcbi"
export REGISTRATION_KEY="replace-with-a-secure-string"
export PORTAL_URL="http://localhost:10000"

python portal/app.py
# Open http://localhost:10000
```

With Docker and Make, the short version is: / Docker, Make ашиглавал:

```bash
make up         # start PostgreSQL
make check-db   # check the database connection
make run        # start the portal
make down       # stop PostgreSQL
```

The tables are created automatically when the portal starts. / Портал асахад хүснэгтүүд автоматаар үүснэ.

### Environment variables / Орчны хувьсагчид

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `REGISTRATION_KEY` | Admin key (approve organizations, edit records, export all data). Keep it private; organizations sign in with their own email and password. |
| `PORTAL_URL` | Public URL used inside QR codes. Default `https://passport.mcbis.org`. Keep it permanent: printed QR labels last as long as the batteries. |
| `LOCAL_TIMEZONE` | Optional, default `Asia/Ulaanbaatar` |

⚠️ **Never commit real keys to GitHub.** On Render, set them under *Environment* in the service settings.
**Жинхэнэ түлхүүрийг GitHub-д хэзээ ч бүү оруул.** Render дээр *Environment* хэсэгт тохируулна.

---

## Repository structure / Бүтэц

```
MCBI-EPR-system/
├── portal/
│   ├── app.py                         # The portal (Gradio + PostgreSQL)
│   └── requirements.txt
├── scripts/check_db.py                # Database connection check
├── docker-compose.yml                 # Local PostgreSQL
├── Makefile
├── .env.example                       # Example settings (no real secrets)
├── MCBI_pilot_phases_interactive.html # Pilot phases visualization
├── diagrams/
└── README-EN.md                       # Full EPR system concept (English)
```

---

## Roadmap / Цаашдын төлөвлөгөө

Done / Хийгдсэн:
- [x] Battery registration with unique ID and QR code
- [x] Public QR lookup and private admin records
- [x] Lifecycle status tracking with full history
- [x] Record corrections with audit trail
- [x] `SLI` category for car starter batteries
- [x] Organization accounts with administrator approval
- [x] Bulk registration from CSV, with QR labels in a ZIP file
- [x] CSV data export
- [x] EPR market reports (units and weight per year and category)
- [x] Three access levels and a JSON API
- [x] Duplicate serial number protection
- [x] Permanent QR address on passport.mcbis.org

Next / Дараагийн алхам:
- [ ] Accounts for collection points
- [ ] Dashboard: registrations by category and status
- [ ] EPR fee simulation (scenarios only, no payments)
- [ ] Pilot report for the Ministry of Environment and Climate Change

---

## Related work / Холбоотой бүтээлүүд

- **EPR law proposal for batteries and battery waste** (independent draft, not an official government document) / Батарей, батарейн хаягдлын EPR хуулийн төсөл (бие даасан санал)
- Full EPR system concept: [README-EN.md](README-EN.md)
- MCBI: https://mcbis.org

---

## Author / Зохиогч

**Enkhtsetseg Shirendev (Enji)**
Founder & CEO, Mongolia Circular Battery Initiative (MCBI)
ORCID: [0009-0006-2212-9309](https://orcid.org/0009-0006-2212-9309) · GitHub: [@Shirendev1](https://github.com/Shirendev1)

Questions, pilot participation or partnership: please open an [issue](https://github.com/Shirendev1/MCBI-EPR-system/issues) or contact MCBI through https://mcbis.org.
Асуулт, туршилтад оролцох эсвэл хамтран ажиллах санал байвал [issue](https://github.com/Shirendev1/MCBI-EPR-system/issues) нээх эсвэл mcbis.org-оор холбогдоно уу.

---

## License / Лиценз

No license has been chosen yet, so all rights are reserved by the author. Contact the author before reusing the code.
Лиценз хараахан сонгогдоогүй тул бүх эрх зохиогчид хамаарна. Кодыг ашиглахаас өмнө зохиогчтой холбогдоно уу.
