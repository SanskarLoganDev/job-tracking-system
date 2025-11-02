import os
import re
import ssl
import smtplib
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
JOBS_ROOT = "https://www.amazon.jobs"  # use root to join job paths
ROLE_KEYWORDS = ["software", "developer", "engineer"]  # case-insensitive
HTTP_TIMEOUT = 30
MAX_RESULTS = 250

# ------------------------------
# Date parsing helpers
# ------------------------------
DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
RELATIVE_RE = re.compile(r"(\d+)\s+(day|days|hour|hours|week|weeks|month|months)\s+ago", re.I)
ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

def parse_possible_date(text: str):
    """Return (posted_text, posted_at_dt or None)."""
    if not text:
        return None, None
    m_iso = ISO_DATE_RE.search(text)
    if m_iso:
        try:
            return m_iso.group(1), datetime.strptime(m_iso.group(1), "%Y-%m-%d")
        except Exception:
            pass
    m = DATE_RE.search(text)
    if m:
        try:
            return m.group(1), datetime.strptime(m.group(1), "%m/%d/%Y")
        except Exception:
            pass
    m2 = RELATIVE_RE.search(text)
    if m2:
        n = int(m2.group(1))
        unit = m2.group(2).lower()
        delta = {
            "hour": timedelta(hours=n), "hours": timedelta(hours=n),
            "day": timedelta(days=n), "days": timedelta(days=n),
            "week": timedelta(weeks=n), "weeks": timedelta(weeks=n),
            "month": timedelta(days=30*n), "months": timedelta(days=30*n),
        }[unit]
        return m2.group(0), datetime.utcnow() - delta
    return None, None

# ------------------------------
# Link normalization
# ------------------------------
JOB_PATH_RE = re.compile(r"^(/en)?/jobs/")  # matches "/en/jobs/..." or "/jobs/..."

def normalize_job_link(link: str) -> str:
    """Return a canonical amazon.jobs job page URL or '' if not a job page."""
    if not link:
        return ""
    link = link.strip()
    # If it's an absolute amazon.jobs URL but not a job page, reject
    if link.startswith("http"):
        if "amazon.jobs" in link and "/jobs/" in link:
            return link
        else:
            return ""  # reject account.amazon.com or other non-job domains
    # Relative path
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
# JSON attempt (prefer job_path over next_step)
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

                # Prefer job page path over "next step / apply" links
                link = (it.get("job_path") or it.get("absolute_url") or "").strip()
                if not link:
                    # last resort (may be account.amazon.com -> reject later)
                    link = (it.get("apply_url") or it.get("url_next_step") or "").strip()

                link = normalize_job_link(link)
                if not link:
                    continue  # skip non-job links

                location = (it.get("location") or it.get("normalized_location")
                            or it.get("city") or "") or ""
                posted_text = (it.get("posted_date") or it.get("posting_date")
                               or it.get("posted_at") or "")
                _, posted_at = parse_possible_date(str(posted_text))

                jobs.append({
                    "title": title,
                    "company": COMPANY_NAME,
                    "location": location,
                    "link": link,
                    "posted_text": str(posted_text) if posted_text else "",
                    # keep posted_at internally; we won't display the ISO column now
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
        raw_href = a["href"].strip()
        link = normalize_job_link(raw_href)
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
        posted_text, _ = parse_possible_date(block_text)
        jobs.append({
            "title": title,
            "company": COMPANY_NAME,
            "location": location,
            "link": link,
            "posted_text": posted_text or "",
        })
    uniq = {(j["title"], j["link"]): j for j in jobs}
    return list(uniq.values())

def try_amazon_html(s: requests.Session) -> list[dict]:
    jobs = []
    # Category page
    try:
        r = s.get(urljoin(BASE_URL, "job_categories/software-development"), timeout=HTTP_TIMEOUT)
        if r.ok:
            jobs += extract_from_html_listings(r.text)
    except Exception:
        pass
    # Search variations
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

def fetch_amazon_jobs() -> list[dict]:
    s = make_session()
    jobs = try_amazon_json(s)
    if jobs:
        return jobs[:MAX_RESULTS]
    return try_amazon_html(s)

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
            <h2>Manual test — {COMPANY_NAME} careers</h2>
            <p>Filter: {", ".join(ROLE_KEYWORDS)}</p>
            <table border="1" cellpadding="6" cellspacing="0">
              <tr><th>Title</th><th>Location</th><th>Posted</th></tr>
              {rows}
            </table>
            <p>Total: {len(jobs)}</p>
            """
        else:
            html = f"<h2>No matches found for {COMPANY_NAME}</h2><p>Filter: {', '.join(ROLE_KEYWORDS)}</p>"

        send_email_html(
            recipient=recipient,
            subject=f"[Job Watch TEST] {COMPANY_NAME} software/dev roles (manual run)",
            html=html,
        )
        return (f"Sent email to {recipient} with {len(jobs)} item(s).", 200)

    except Exception as e:
        return (f"Error: {e}", 500)
