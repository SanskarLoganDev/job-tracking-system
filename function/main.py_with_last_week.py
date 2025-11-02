import os
import re
import ssl
import smtplib
import json
from datetime import datetime, timedelta
from urllib.parse import urljoin
from email.message import EmailMessage

import requests
from bs4 import BeautifulSoup

# ------------------------------
# Config (hard-coded for this test)
# ------------------------------
COMPANY_NAME = "Amazon"
BASE_URL = "https://www.amazon.jobs/en/"
JOBS_ROOT = "https://www.amazon.jobs"
ROLE_KEYWORDS = ["software", "developer", "engineer"]  # case-insensitive
HTTP_TIMEOUT = 30
MAX_RESULTS = 250

# Age filter
MAX_AGE_DAYS = 7
# How many detail pages to hit to discover dates
DETAIL_FETCH_LIMIT = 40

# ------------------------------
# Date parsing helpers
# ------------------------------
DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")  # 10/31/2025
RELATIVE_RE = re.compile(r"(\d+)\s+(day|days|hour|hours|week|weeks|month|months)\s+ago", re.I)
ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")  # 2025-10-31
MONTH_NAME_DATE_RE = re.compile(  # Oct 31, 2025
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+"
    r"(\d{1,2}),\s*(\d{4})\b",
    re.I,
)

MONTH_INDEX = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12
}

def parse_possible_date(text: str):
    """Return (posted_text, posted_dt or None) from mixed text (supports ISO, MM/DD/YYYY, 'Oct 31, 2025', or 'X days ago')."""
    if not text:
        return None, None

    # ISO first
    m_iso = ISO_DATE_RE.search(text)
    if m_iso:
        try:
            return m_iso.group(1), datetime.strptime(m_iso.group(1), "%Y-%m-%d")
        except Exception:
            pass

    # Month name form
    m_name = MONTH_NAME_DATE_RE.search(text)
    if m_name:
        try:
            mon = MONTH_INDEX[m_name.group(1).lower()]
            day = int(m_name.group(2))
            yr = int(m_name.group(3))
            dt = datetime(year=yr, month=mon, day=day)
            return m_name.group(0), dt
        except Exception:
            pass

    # MM/DD/YYYY
    m = DATE_RE.search(text)
    if m:
        try:
            return m.group(1), datetime.strptime(m.group(1), "%m/%d/%Y")
        except Exception:
            pass

    # Relative "X days ago"
    m2 = RELATIVE_RE.search(text)
    if m2:
        n = int(m2.group(1))
        unit = m2.group(2).lower()
        delta = {
            "hour": timedelta(hours=n), "hours": timedelta(hours=n),
            "day": timedelta(days=n),   "days": timedelta(days=n),
            "week": timedelta(weeks=n), "weeks": timedelta(weeks=n),
            "month": timedelta(days=30*n), "months": timedelta(days=30*n),
        }[unit]
        return m2.group(0), datetime.utcnow() - delta

    return None, None

def parse_iso_dt(s: str):
    if not s:
        return None
    s = s.strip().replace("Z", "")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        m = ISO_DATE_RE.search(s)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d")
            except Exception:
                return None
        return None

# ------------------------------
# Link normalization
# ------------------------------
JOB_PATH_RE = re.compile(r"^(/en)?/jobs/")  # "/en/jobs/..." or "/jobs/..."

def normalize_job_link(link: str) -> str:
    """Return canonical amazon.jobs job URL or '' if not a job page."""
    if not link:
        return ""
    link = link.strip()
    if link.startswith("http"):
        if "amazon.jobs" in link and "/jobs/" in link:
            return link
        return ""  # reject non-job domains (e.g., account.amazon.com)
    if JOB_PATH_RE.search(link):
        return urljoin(JOBS_ROOT, link)
    return ""

# ------------------------------
# Session / headers
# ------------------------------
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/119.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                  "application/json;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.amazon.jobs/en/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    try:
        s.get(BASE_URL, timeout=HTTP_TIMEOUT)  # warm-up cookies
    except Exception:
        pass
    return s

# ------------------------------
# JSON attempt (prefer job_path over apply links)
# ------------------------------
def try_amazon_json(s: requests.Session) -> list[dict]:
    candidates = [
        ("https://www.amazon.jobs/en/search.json",
         [("result_limit", "100"), ("offset", "0"), ("category[]", "Software Development")]),
        ("https://www.amazon.jobs/en/search.json",
         [("result_limit", "100"), ("offset", "0"), ("job_category[]", "Software Development")]),
        ("https://www.amazon.jobs/en/search.json",
         [("result_limit", "100"), ("offset", "0"), ("query", "software")]),
    ]
    jobs = []
    for url, params in candidates:
        try:
            r = s.get(url, params=params, timeout=HTTP_TIMEOUT)
            if not r.ok:
                continue
            data = r.json()
        except Exception:
            continue

        lists = []
        if isinstance(data, dict):
            for key in ("jobs", "search_results", "results", "hits", "items"):
                if key in data and isinstance(data[key], list):
                    lists.append(data[key])
            if not lists:
                for v in data.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        lists.append(v)

        for lst in lists:
            for it in lst:
                title = (it.get("title") or it.get("job_title") or "").strip()
                if not title or not any(k in title.lower() for k in ROLE_KEYWORDS):
                    continue
                link = (it.get("job_path") or it.get("absolute_url") or "").strip()
                if not link:
                    link = (it.get("apply_url") or it.get("url_next_step") or "").strip()
                link = normalize_job_link(link)
                if not link:
                    continue
                location = (it.get("location") or it.get("normalized_location")
                            or it.get("city") or "") or ""
                posted_text = (it.get("posted_date") or it.get("posting_date")
                               or it.get("posted_at") or "")
                _, posted_dt = parse_possible_date(str(posted_text))
                jobs.append({
                    "title": title,
                    "company": COMPANY_NAME,
                    "location": location,
                    "link": link,
                    "posted_text": str(posted_text) if posted_text else "",
                    "_posted_dt": posted_dt,  # keep dt for filtering
                })
        if jobs:
            break

    uniq = {(j["title"], j["link"]): j for j in jobs if j.get("link")}
    return list(uniq.values())[:MAX_RESULTS]

# ------------------------------
# HTML fallback (anchors that are job paths)
# ------------------------------
def extract_from_html_listings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)
    jobs = []
    for a in anchors:
        link = normalize_job_link(a["href"].strip())
        if not link:
            continue
        title = a.get_text(strip=True)
        if not title or not any(k in title.lower() for k in ROLE_KEYWORDS):
            continue
        parent = a.find_parent()
        block_text = parent.get_text(" ", strip=True) if parent else title
        location = ""
        for kw in ["United States", "India", "Canada", "Remote", "Hybrid",
                   "Seattle", "Bangalore", "Hyderabad"]:
            if kw in block_text:
                location = kw
                break
        posted_text, posted_dt = parse_possible_date(block_text)
        jobs.append({
            "title": title,
            "company": COMPANY_NAME,
            "location": location,
            "link": link,
            "posted_text": posted_text or "",
            "_posted_dt": posted_dt,
        })
    uniq = {(j["title"], j["link"]): j for j in jobs}
    return list(uniq.values())

def try_amazon_html(s: requests.Session) -> list[dict]:
    jobs = []
    try:
        r = s.get(urljoin(BASE_URL, "job_categories/software-development"), timeout=HTTP_TIMEOUT)
        if r.ok:
            jobs += extract_from_html_listings(r.text)
    except Exception:
        pass
    try:
        r = s.get(urljoin(BASE_URL, "search"), params={"category": "Software Development"}, timeout=HTTP_TIMEOUT)
        if r.ok:
            jobs += extract_from_html_listings(r.text)
    except Exception:
        pass
    try:
        r = s.get(urljoin(BASE_URL, "search"), params={"query": "software"}, timeout=HTTP_TIMEOUT)
        if r.ok:
            jobs += extract_from_html_listings(r.text)
    except Exception:
        pass
    uniq = {(j["title"], j["link"]): j for j in jobs}
    return list(uniq.values())[:MAX_RESULTS]

# ------------------------------
# Enrich missing posting dates from detail page
# ------------------------------
UPDATED_LABEL_RE = re.compile(
    r"(Updated|Posted)\s*:?\s*(?P<date>(?:\d{4}-\d{2}-\d{2})|(?:\d{1,2}/\d{1,2}/\d{4})|"
    r"(?:[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}))",
    re.I,
)

def enrich_posted_dates(jobs: list[dict], s: requests.Session):
    fetched = 0
    for j in jobs:
        if j.get("_posted_dt"):
            continue
        if fetched >= DETAIL_FETCH_LIMIT:
            break
        link = j.get("link")
        if not link:
            continue
        try:
            r = s.get(link, timeout=HTTP_TIMEOUT)
            if not r.ok:
                continue
            soup = BeautifulSoup(r.text, "html.parser")

            # 1) JSON-LD datePosted / dateModified
            found = False
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or script.text or "{}")
                except Exception:
                    continue
                objs = data if isinstance(data, list) else [data]
                for obj in objs:
                    if isinstance(obj, dict):
                        for key in ("datePosted", "dateModified"):
                            if key in obj:
                                ds = str(obj[key])
                                txt, dt = parse_possible_date(ds)
                                if dt:
                                    j["_posted_dt"] = dt
                                    j["posted_text"] = txt or ds
                                    found = True
                                    break
                    if found:
                        break
                if found:
                    break

            # 2) Meta tags (common on some sites)
            if not j.get("_posted_dt"):
                for name in ("article:published_time", "article:modified_time", "og:updated_time"):
                    m = soup.find("meta", attrs={"property": name})
                    if m and m.get("content"):
                        txt, dt = parse_possible_date(m["content"])
                        if dt:
                            j["_posted_dt"] = dt
                            j["posted_text"] = txt or m["content"]
                            found = True
                            break

            # 3) Visible "Updated: ..." or "Posted: ..." text
            if not j.get("_posted_dt"):
                text = soup.get_text(" ", strip=True)
                m = UPDATED_LABEL_RE.search(text)
                if m:
                    ds = m.group("date")
                    txt, dt = parse_possible_date(ds)
                    if dt:
                        j["_posted_dt"] = dt
                        j["posted_text"] = f"{m.group(1).title()}: {ds}"

            # 4) Last fallback: anything that looks like a date
            if not j.get("_posted_dt"):
                txt, dt = parse_possible_date(soup.get_text(" ", strip=True))
                if dt:
                    j["_posted_dt"] = dt
                    if not j.get("posted_text"):
                        j["posted_text"] = txt or ""
        except Exception:
            pass
        fetched += 1

# ------------------------------
# Filter by age (<= MAX_AGE_DAYS)
# ------------------------------
def filter_by_age(jobs: list[dict]) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(days=MAX_AGE_DAYS)
    fresh = []
    for j in jobs:
        dt = j.get("_posted_dt")
        if not dt:
            # NEW: also try parsing posted_text with full parser (not just ISO)
            _, dt = parse_possible_date(j.get("posted_text", ""))
        if dt and dt >= cutoff:
            fresh.append(j)
    return fresh

# ------------------------------
# Fetch + filter
# ------------------------------
def fetch_amazon_jobs() -> list[dict]:
    s = make_session()
    jobs = try_amazon_json(s)
    if not jobs:
        jobs = try_amazon_html(s)
    enrich_posted_dates(jobs, s)        # ensure we have dates when possible
    jobs = filter_by_age(jobs)          # keep only recent
    return jobs[:MAX_RESULTS]

# ------------------------------
# Email helper (no CSV)
# ------------------------------
def send_email_html(recipient: str, subject: str, html: str):
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if not smtp_user or not smtp_pass:
        raise RuntimeError("Missing SMTP_USER/SMTP_PASS env vars")

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content("Your client does not support HTML.")
    msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls(context=ctx)
        s.login(smtp_user, smtp_pass.replace(" ", ""))
        s.send_message(msg)

# ------------------------------
# HTTP entry point (2nd gen)
# ------------------------------
def scan_jobs_test(request):
    recipient = os.getenv("RECIPIENT_EMAIL")
    if not recipient:
        return ("Missing RECIPIENT_EMAIL env var", 500)

    try:
        jobs = fetch_amazon_jobs()
        if jobs:
            rows = "".join(
                f'<tr>'
                f'<td><a href="{j["link"]}">{j["title"]}</a></td>'
                f'<td>{j.get("location","")}</td>'
                f'<td>{j.get("posted_text","")}</td>'
                f'</tr>'
                for j in jobs
            )
            html = f"""
            <h2>Manual test — {COMPANY_NAME} careers (last {MAX_AGE_DAYS} days)</h2>
            <p>Filter: {", ".join(ROLE_KEYWORDS)}</p>
            <table border="1" cellpadding="6" cellspacing="0">
              <tr><th>Title</th><th>Location</th><th>Posted / Updated</th></tr>
              {rows}
            </table>
            <p>Total (fresh): {len(jobs)}</p>
            """
        else:
            html = (f"<h2>No recent matches (≤ {MAX_AGE_DAYS} days) for {COMPANY_NAME}</h2>"
                    f"<p>Filter: {', '.join(ROLE_KEYWORDS)}</p>")

        send_email_html(
            recipient=recipient,
            subject=f"[Job Watch TEST] {COMPANY_NAME} software/dev roles (≤{MAX_AGE_DAYS}d)",
            html=html,
        )
        return (f"Sent email to {recipient} with {len(jobs)} recent item(s).", 200)

    except Exception as e:
        return (f"Error: {e}", 500)
