# HustleHUB – JobWatch (Local)

Lightweight, local-first job watcher to **track a company’s careers page** and **email you fresh roles**—no third-party job boards, no cloud bill. This hackathon build currently supports **Amazon (amazon.jobs)** end-to-end; the code and data model are structured to add more companies next.

---

# Team

Abhigna Kandala
Krishnendra Tomar
Heena Khan
Sanskar Vidyarthi

## 🧩 Problem Statement

Targeted job hunting is tedious: you must repeatedly check specific companies’ career pages, apply keyword filters, and figure out which postings are actually **new**. Job boards add noise, and many teams publish roles only on their own site.

**We want a simple, no-cost tool** that:

* Stores companies & their careers URLs locally,
* Pulls job postings directly from those pages,
* Filters by role keywords and **recently posted**,
* Emails a clean summary to you.

---

## ✅ Our Solution

* **Backend:** FastAPI app with a small **SQLite** database (SQLAlchemy).
* **Frontend:** A minimal HTML/CSS page (no framework) to add companies and trigger runs.
* **Scraper:** Requests + BeautifulSoup tuned to **amazon.jobs** (with date extraction & age filtering).
* **Email:** SMTP (e.g., Gmail with App Password) sends you an HTML table of fresh roles.
* **Config via `.env`:** SMTP creds + recipient email; no secrets in code.

> For the hackathon scope, the live scraper is implemented for **Amazon**. The DB & scraper plumbing are extensible so you can add parsers for other career sites next.

---

## 🏗️ Architecture (Local)

```
┌────────────┐     POST /companies           ┌─────────────┐
│ Frontend   │ ───────────────────────────▶  │  FastAPI    │
│ (index.html│  GET /companies               │  app.py     │
│ static/*)  │ ◀───────────────────────────  │             │
│            │     POST /run/{id}[?dry_run]  │             │
└─────┬──────┘                               └─────┬───────┘
      │                                          │
      │                              SQLAlchemy  │
      │                                          ▼
      │                                      SQLite
      │                                     jobs.db
      │
      │                 scrape amazon.jobs (requests+bs4)
      ▼
  HTML email  ◀──────────── SMTP (Gmail/others) ────────────┐
  (summary)                                                  │
                                                             │
                                          .env (SMTP + recipient)
```

---

## 📁 Project Structure

```
.
├─ app.py                  # FastAPI app (API, scraper, email)
├─ requirements.txt        # Python deps
├─ .env.example            # Sample environment variables (copy to .env)
├─ templates/
│   └─ index.html          # UI to add companies and trigger runs
└─ static/
    ├─ styles.css          # UI styles
    └─ script.js           # (optional) UI helpers if used
```

> `jobs.db` (SQLite) is created at runtime in the project root.

---

## 🔧 Setup & Run

### 1) Python env

```bash
# macOS/Linux
python -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2) Install deps

```bash
pip install -r requirements.txt
```

`requirements.txt` (reference)

```
fastapi
uvicorn[standard]
jinja2
sqlalchemy
requests
beautifulsoup4
python-dotenv
```

### 3) Configure `.env`

Create a `.env` file (copy from `.env.example`) and fill:

```
# Gmail example (requires 2FA + App Password)
SMTP_USER=yourname@gmail.com
SMTP_PASS=abcd efgh ijkl mnop   # 16-char App Password; spaces OK
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

# Where we send the job summary email
RECIPIENT_EMAIL=you@example.com
```

> **Gmail note:** You must enable 2-Step Verification and generate an **App Password**. Your normal account password won’t work with SMTP.

### 4) Start server

```bash
uvicorn app:app --reload
```

Visit: `http://127.0.0.1:8000/`

---

## 🖥️ Using the App

1. Open the UI (`/`).
2. **Add a company** (for this prototype, add **Amazon**):

   * Name: `Amazon`
   * Careers/List URL: `https://www.amazon.jobs/en/search?category=Software%20Development`
   * Role keywords: `software,developer,engineer`
   * Max age (days): e.g., `7`
   * Detail fetch limit: `40` (how many detail pages to open to discover dates)
3. After saving, click **Email** (or hit the endpoint below).

### API (optional)

* List companies
  `GET /companies`

* Add a company
  `POST /companies`

  ```json
  {
    "name": "Amazon",
    "list_url": "https://www.amazon.jobs/en/search?category=Software%20Development",
    "role_keywords": "software,developer,engineer",
    "max_age_days": 7,
    "detail_fetch_limit": 40,
    "active": true
  }
  ```

* Preview (dry-run, returns JSON, **no email**):
  `POST /run/{id}?dry_run=1`

* Send email (uses `RECIPIENT_EMAIL` from `.env`):
  `POST /run/{id}`

* Delete a company
  `DELETE /companies/{id}`

* Clear all companies
  `POST /companies/reset`

---

## ✨ What It Does Today

* Stores companies locally in SQLite.
* Fetches Amazon listings via `/search.json` and HTML fallbacks.
* Normalizes real job links (rejects non-job domains).
* Parses & enriches posting dates from JSON-LD, meta tags, and visible text.
* Filters to **fresh** roles (≤ `max_age_days`).
* Emails a clean HTML table to `RECIPIENT_EMAIL`.

---

## 🧪 Troubleshooting

* **No email arrives**

  * Check server logs for `SMTP auth failed`. If using Gmail, you must use a **16-char App Password** (not your normal password).
  * Confirm `.env` values are loaded (restart `uvicorn` after edits).
  * Firewalls/VPNs can block SMTP ports (587/465).

* **0 jobs but you expect some**

  * Increase `detail_fetch_limit` to discover dates on more detail pages.
  * Lower `max_age_days` filter to widen or narrow results.
  * Keywords are applied to titles—adjust `role_keywords`.

* **Reset companies**
  Use `POST /companies/reset` or delete the row via your UI flow.

---

## 🚧 Limitations (Hackathon scope)

* Live scraper implemented for **Amazon**. Other sites will need tailored parsers or a headless browser for JS-heavy pages.
* No deduplication across runs beyond URL/title combos per run.
* No auth/user management; `.env` holds credentials locally.

---

## 🛣️ Future Scope

1. **Multi-company scrapers**

   * Add adapters for each domain (e.g., `scrapers/google.py`, `scrapers/adp.py`, `scrapers/greenhouse.py`).
   * Pluggable registry based on `netloc`, with shared date/HTML utils.

2. **Headless browser support**

   * Use Playwright/Selenium for pages rendering jobs via JS.
   * Keep Requests/BS4 path as fast default.

3. **Persistence & dedupe**

   * Store discovered jobs with a hash to avoid emailing repeats.
   * “New since last email” rollups.

4. **Scheduling & Cloud**

   * Bring back GCP version: Cloud Scheduler → Pub/Sub → Cloud Run/Functions → Firestore → Email.
   * Add retries, metrics, and alerting.

5. **Front-end polish**

   * Rich filters, pagination, and “Preview before email.”
   * Per-company recipient overrides, tags, and status badges.

6. **Safety & Compliance**

   * Rotation for SMTP secrets, OAuth mail APIs, rate limiting.
   * Respect robots.txt / site terms; implement backoff & caching.

---

## 📜 License

MIT (or your preference). Keep `.env` and any secrets **out of version control**.

---

## 🙌 Credits

Built fast with **FastAPI**, **SQLite/SQLAlchemy**, **Requests + BeautifulSoup**, and a tiny HTML/CSS front end. Perfect for hackathon demos and a solid base to evolve into a proper multi-company watcher.
