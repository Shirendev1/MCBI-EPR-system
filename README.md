# MCBI – Mongolia's EPR System
# MCBI – Монголын EPR систем

---

## Overview / Ерөнхий мэдээлэл

This repository contains foundational documents for developing a circular economy framework, battery waste management, and an Extended Producer Responsibility (EPR) system in Mongolia.

Энэ репозиторт Монголд тойрог эдийн засгийн тогтолцоо, батарейн хаягдлын менежмент болон үйлдвэрлэгчийн ...

---

## Purpose / Зорилго

**English:**

To develop a responsible system for collecting, reusing, and recycling batteries and other waste in Mongolia. The system aims to support producer accountability, reliable data management, sustaina...

**Монгол:**

Монголд батарей болон бусад хаягдлыг хариуцлагатайгаар цуглуулах, дахин ашиглах, дахин боловсруулах тогт...

---

## Contents / Агуулга

- **EPR Policy Proposals** / EPR-ийн бодлогын саналууд
- **Circular Economy System Model** / Тойрог эдийн засгийн тогтолцооны загвар
- **Data Collection Structure** / Өгөгдөл цуглуулах бүтэц
- **Reporting Templates** / Тайлагналын загварууд
- **Diagrams and Appendices** / Диаграм ба хавсралтууд

---

## Core Concept / Гол санаа

**English:**

EPR connects producer responsibility, data governance, financing, infrastructure, and consumer participation across the product lifecycle. It helps define who is responsible for products and mater...

**Монгол:**

EPR нь бүтээгдэхүүний амьдралын мөчлөгийн турш үйлдвэрлэгчийн хариуцлага, өгөгдлийн удирдлага, санхүүжилт,...

---

## Project Structure / Төслийн бүтэц

```
MCBI-EPR-system/
├── README.md                           # Bilingual overview / Хоёр хэл дээрх танилцуулга
├── README-EN.md                        # English documentation / Англи хэл дээрх баримт бичиг
├── MCBI_pilot_phases_interactive.html  # Pilot phases visualization / Туршилтын үе шатуудын дүрслэл
└── diagrams/                           # Diagrams / Диаграмууд
    └── README.md
```

---

## Getting Started / Эхлэх

1. Read the documentation overview / Баримт бичгийн ерөнхий бүтэцтэй танилцах
2. Explore the interactive visualization / Интерактив дүрслэлийг үзэх
3. Review the system diagrams / Системийн диаграмуудыг судлах
4. Consult the policy proposals for further detail / Дэлгэрэнгүй мэдээллийг бодлогын саналаас үзэх

---

## English Documentation / Англи хэл дээрх баримт бичиг

For more detailed English documentation, see **[README-EN.md](README-EN.md)**.

Англи хэл дээрх дэлгэрэнгүй мэдээллийг **[README-EN.md](README-EN.md)** файлаас үзнэ үү.

---

## License / Лиценз

A license has not yet been specified for this repository.

Энэ репозиторт ашиглалтын лиценз одоогоор заагаагүй байна.

---

## Contact / Холбоо барих

For questions or contributions, please contact the repository owner.

Асуулт болон хамтран ажиллах санал байвал репозиторийн эзэмшигчтэй холбогдоно уу.

---

## How to run (locally or on Render)

For local setup:

1. Create and activate a Python virtual environment:

   ```bash
   python -m venv .venv
   ```

   Activate the virtual environment:
   - Linux/macOS: `source .venv/bin/activate`
   - Windows PowerShell: `.venv\Scripts\Activate.ps1`

2. Install dependencies:

   ```bash
   pip install -r portal/requirements.txt
   ```

3. Provide the required environment variables (example values are shown in `.env.example`):

   - `DATABASE_URL` (PostgreSQL connection string)
   - `REGISTRATION_KEY` (admin secret used to protect private actions)
   - `PORTAL_URL` (public-facing portal URL, used when generating QR codes)

   Example (Linux/macOS):

   ```bash
   export DATABASE_URL="postgresql://mcbi:mcbi_pass@localhost:5432/mcbi"
   export REGISTRATION_KEY="replace-with-a-secure-string"
   export PORTAL_URL="http://localhost:10000"
   ```

4. Run the portal:

   ```bash
   python portal/app.py
   ```

Notes

- PostgreSQL must be running and reachable using the `DATABASE_URL` you provide. You can start a local Postgres instance with Docker if you prefer (for example, `docker run --name mcbi-postgres -e POSTGRES_PASSWORD=mcbi_pass -e POSTGRES_USER=mcbi -e POSTGRES_DB=mcbi -p 5432:5432 -d postgres`).
- The application calls `init_database()` on startup; it will create the required tables automatically if they do not already exist.
- Do not commit real secrets. The `REGISTRATION_KEY` is sensitive and must never be committed to GitHub. Use environment variables or your deployment platform's secret management.
- On Render (or other PaaS), set `DATABASE_URL`, `REGISTRATION_KEY`, and `PORTAL_URL` as environment variables/secrets in the service settings instead of committing them to the repo.

---

## English Documentation / Англи хэл дээрх баримт бичиг

For more detailed English documentation, see **[README-EN.md](README-EN.md)**.

---

