import os
import re
import csv
import io
import ssl
import smtplib
from datetime import datetime, timedelta
from urllib.parse import urljoin
from email.message import EmailMessage

import requests
from bs4 import BeautifulSoup


# ==============================
# Configuration (hard-coded for test)
# ==============================
COMPANY_NAME = "ADP"
CAREERS_URL = "https://amazon.jobs/content/en/job-categories/software-development"
ROLE_KEYWORDS = ["software", "developer", "engineer"]  # case-insensitive
HTTP_TIMEOUT = 30
MAX_RESULTS = 200  # safety cap so your email doesn't explode


# ==============================
# Date parsing helpers
# ==============================
DATE_RE = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")
RELATIVE_RE = re.compile(r"(\d+)\s+(day|days|hour|hours|week|weeks|month|months)\s+ago", re.I)

def parse_possible_date(text: str):
    """
    Try to find a date or relative phrase in free text.
    Returns (posted_text, posted_at_dt | None).
    """
    if not text:
        return None, None

    # Absolute date e.g. 10/31/2025
    m = DATE_RE.search(text)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%m/%d/%Y")
            return m.group(1), dt
        except Exception:
            pass

    # Relative e.g. "5 days ago"
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


# ==============================
# Scraping helpers
# ==============================
def extract_jobs_from_html(html: str, base_url: str) -> list[dict]:
    """
    Heuristic parser:
      - find anchors that look like job titles
      - keep only titles matching ROLE_KEYWORDS
      - try to grab nearby location + posted info
    Works for many listing pages; for production you'd use site-specific selectors.
    """
    soup = BeautifulSoup(html, "lxml")

    # Prefer likely job title elements; fallback to all anchors
    title_nodes = soup.find_all(lambda tag: (
        tag.name in ("a", "h3", "h2", "span", "div") and
        (
            ("job" in " ".join([str(v).lower() for v in tag.attrs.values()])) or
            ("title" in " ".join([str(v).lower() for v in tag.attrs.values()]))
        )
    ))
    anchors = []
    for n in title_nodes:
        a = n if (n.name == "a" and n.get("href")) else n.find("a", href=True)
        if a and a.get_text(strip=True):
            anchors.append(a)

    if not anchors:
        anchors = soup.find_all("a", href=True)

    jobs = []
    for a in anchors:
        title = a.get_text(strip=True)
        if not title:
            continue

        if not any(k in title.lower() for k in ROLE_KEYWORDS):
            continue

        href = a["href"]
        link = href if href.startswith("http") else urljoin(base_url, href)

        # Nearby context for location/date
        parent = a.find_parent()
        block_text = parent.get_text(" ", strip=True) if parent else title

        location = ""
        for kw in ["United States", "India", "Canada", "Remote", "Hybrid"]:
            if kw in block_text:
                location = kw
                break

        posted_text, posted_at = parse_possible_date(block_text)

        jobs.append({
            "title": title,
            "company": COMPANY_NAME,
            "location": location,
            "link": link,
            "posted_text": posted_text or "",
            "posted_at": posted_at.isoformat() + "Z" if posted_at else None,
        })

    # Deduplicate by (title, link)
    uniq = {(j["title"], j["link"]): j for j in jobs}
    return list(uniq.values())


def fetch_adp_jobs() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0"}
    all_jobs: list[dict] = []

    # Base listing
    r = requests.get(CAREERS_URL, headers=headers, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    all_jobs += extract_jobs_from_html(r.text, CAREERS_URL)

    # Try a few keyword pages (if the site supports ?q=)
    for q in ["software", "engineer", "developer"]:
        try:
            rq = requests.get(f"{CAREERS_URL}?q={q}", headers=headers, timeout=HTTP_TIMEOUT)
            if rq.ok:
                all_jobs += extract_jobs_from_html(rq.text, CAREERS_URL)
        except Exception:
            pass

    # Keep only matching titles (defensive)
    filtered = [j for j in all_jobs if any(k in j["title"].lower() for k in ROLE_KEYWORDS)]

    # Final dedup & cap
    uniq = {(j["title"], j["link"]): j for j in filtered}
    jobs = list(uniq.values())
    return jobs[:MAX_RESULTS]


# ==============================
# Email helper (env vars)
# ==============================
def send_email_html_csv(recipient: str, subject: str, html: str, rows: list[dict]):
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

    if rows:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["title", "company", "location", "link", "posted_text"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        msg.add_attachment(buf.getvalue().encode("utf-8"),
                           maintype="text", subtype="csv", filename="jobs.csv")

    ctx = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls(context=ctx)
        # Gmail app passwords allow whitespace; strip for safety
        s.login(smtp_user, smtp_pass.replace(" ", ""))
        s.send_message(msg)


# ==============================
# HTTP entry point (2nd gen)
# ==============================
def scan_jobs_test(request):
    """
    Manual-test HTTP function:
      - Scrapes ADP careers
      - Filters for software/dev/engineer
      - Emails results to RECIPIENT_EMAIL (env var)
    """
    recipient = os.getenv("RECIPIENT_EMAIL")
    if not recipient:
        return ("Missing RECIPIENT_EMAIL env var", 500)

    try:
        jobs = fetch_adp_jobs()

        if jobs:
            rows_html = "".join(
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
              {rows_html}
            </table>
            <p>Total: {len(jobs)}</p>
            """
        else:
            html = f"<h2>No matches found for {COMPANY_NAME}</h2><p>Filter: {', '.join(ROLE_KEYWORDS)}</p>"

        send_email_html_csv(
            recipient=recipient,
            subject=f"[Job Watch TEST] {COMPANY_NAME} software/dev roles (manual run)",
            html=html,
            rows=jobs,
        )
        return (f"Sent email to {recipient} with {len(jobs)} item(s).", 200)

    except Exception as e:
        # Basic error surfacing; check Cloud Logging for stack traces
        return (f"Error: {e}", 500)
