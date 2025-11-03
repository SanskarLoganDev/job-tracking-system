# HustleHUB – JobWatch (Local)
# TRACK - Productivity and Automation

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
└─ function/
    └─ main.py           # the code for cloud function
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

Here’s a **clean Cloud section** you can paste into your README (it replaces the earlier Pub/Sub content). It assumes **Cloud Scheduler → HTTPS Cloud Function (2nd gen)** every **10 minutes**.

---

## ☁️ Cloud Deployment (GCP) – Scheduler ➜ Cloud Function (HTTP, every 10 min)

Make the app hands-off in the cloud: **Cloud Scheduler** hits your **HTTP Cloud Function** every 10 minutes; the function reads active companies (Firestore/Datastore, if you use it), scrapes, and emails you fresh roles.

### Cloud Architecture

```
         (every 10 minutes)
 Cloud Scheduler  ──────────────▶  Cloud Functions (2nd gen, HTTP)
                                        │
                                        │  requests + BeautifulSoup
                                        ▼
                                   Company Sites
                                        │
                                        ▼
                              SMTP (Gmail / SES / SendGrid)
                                   Email summary

                  ┌─────────────────────────────────────────┐
                  │ Firestore (Datastore mode) — optional   │
                  │   • Store companies & settings          │
                  │   • Function reads/filter by “active”   │
                  └─────────────────────────────────────────┘

                  ┌─────────────────────────────────────────┐
                  │ Secret Manager — recommended            │
                  │   • SMTP_USER / SMTP_PASS / …           │
                  │   • RECIPIENT_EMAIL                     │
                  └─────────────────────────────────────────┘
```

### One-Time Setup

> Replace `$PROJECT_ID`, `$REGION` (e.g., `us-central1`), and emails. Run in **Cloud Shell** or your terminal (with `gcloud`).

1. **Enable APIs**

```bash
gcloud config set project $PROJECT_ID
gcloud services enable cloudfunctions.googleapis.com cloudscheduler.googleapis.com \
  firestore.googleapis.com secretmanager.googleapis.com
```

2. **(Optional) Firestore (Datastore mode)**
   If you want a cloud DB of companies (same shape as local), create Firestore:

```bash
gcloud firestore databases create --region=$REGION
```

Add docs (GUI or code) like:

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

3. **Secrets (recommended)**

```bash
echo -n "yourname@gmail.com" | gcloud secrets create SMTP_USER --data-file=-
echo -n "abcd efgh ijkl mnop" | gcloud secrets create SMTP_PASS --data-file=-  # Gmail App Password (16 chars)
echo -n "smtp.gmail.com"     | gcloud secrets create SMTP_HOST --data-file=-
echo -n "587"                | gcloud secrets create SMTP_PORT --data-file=-
echo -n "you@example.com"    | gcloud secrets create RECIPIENT_EMAIL --data-file=-
```

4. **Deploy the Cloud Function (2nd gen, HTTP)**

> Use your function **entry point name** (e.g., `scan_jobs_test` or whatever your handler is called).

```bash
gcloud functions deploy jobwatch-scan \
  --gen2 \
  --runtime=python312 \
  --region=$REGION \
  --entry-point=scan_jobs_test \
  --trigger-http \
  --allow-unauthenticated=false \
  --set-secrets=SMTP_USER=SMTP_USER:latest,SMTP_PASS=SMTP_PASS:latest,SMTP_HOST=SMTP_HOST:latest,SMTP_PORT=SMTP_PORT:latest,RECIPIENT_EMAIL=RECIPIENT_EMAIL:latest \
  --set-env-vars=PYTHONUNBUFFERED=1
```

Grant the function’s **service account** access to Firestore (if used) and Secrets:

```bash
SA="$(gcloud functions describe jobwatch-scan --gen2 --region $REGION --format='value(serviceConfig.serviceAccountEmail)')"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" \
  --role="roles/datastore.user"

for S in SMTP_USER SMTP_PASS SMTP_HOST SMTP_PORT RECIPIENT_EMAIL; do
  gcloud secrets add-iam-policy-binding $S \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor"
done
```

5. **Create a Scheduler job (every 10 minutes)**

* Create a Scheduler **service account** and allow it to invoke your function:

```bash
gcloud iam service-accounts create scheduler-sa --display-name="Scheduler SA"

# 2nd gen CFs use Cloud Run-style invoker for HTTP
gcloud functions add-iam-policy-binding jobwatch-scan \
  --gen2 --region=$REGION \
  --member="serviceAccount:scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

* Get the function URL and create the job:

```bash
FUNC_URL="$(gcloud functions describe jobwatch-scan --gen2 --region $REGION --format='value(serviceConfig.uri)')"

gcloud scheduler jobs create http jobwatch-10min \
  --schedule="*/10 * * * *" \
  --uri="$FUNC_URL" \
  --http-method=POST \
  --oidc-service-account-email="scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --oidc-token-audience="$FUNC_URL"
```

### Smoke Test

* In **Cloud Functions** UI, copy the **URI** and run:

```bash
curl -X POST "$FUNC_URL"
```

* Or in **Cloud Scheduler**, click **Run now**.
* Check **Cloud Logging** for run output and your inbox for the email.

### Troubleshooting

* **403 Forbidden**: The Scheduler SA likely lacks `roles/run.invoker` on the function. Re-run the IAM binding command above.
* **Secrets not loading**: Ensure the function SA has `roles/secretmanager.secretAccessor` on each secret.
* **SMTP auth failed**: For Gmail, enable **2-Step Verification** and use a **16-char App Password** (not your normal password).
* **No jobs**: Some sites are JS-heavy or block bots; Amazon path here uses JSON + HTML fallbacks. Increase `detail_fetch_limit` or relax `max_age_days`.

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
