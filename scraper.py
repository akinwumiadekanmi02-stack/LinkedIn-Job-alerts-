import os
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

# ================= PRE-CONFIGURED SEARCHES =================
SEARCHES = [
    {"keywords": "Senior Software Engineer", "location": "Nigeria"},
    {"keywords": "Senior Fullstack Engineer", "location": "Nigeria"},
    {"keywords": "Senior Frontend Engineer", "location": "Nigeria"},
    {"keywords": "Senior AI Engineer", "location": "Nigeria"},
    {"keywords": "Software Developer", "location": "Nigeria"},
    {"keywords": "Full Stack Developer", "location": "Nigeria"},
    {"keywords": "Frontend Developer", "location": "Nigeria"},
    {"keywords": "AI Engineer", "location": "Nigeria"},
]

# 86400 = last 24 hours (great for first test)
# Change to "3600" after testing for strict hourly checks
TIME_SECONDS = "86400"

# Title keywords to skip (filters out non-senior & unrelated roles)
EXCLUDE_TITLE_WORDS = [
    "intern", "internship", "junior", "jr", "entry level", "entry-level",
    "graduate", "trainee", "associate", "student", "apprentice", "nysc"
]

# Title must match at least one of these core terms
INCLUDE_TITLE_WORDS = [
    "software", "fullstack", "full-stack", "full stack",
    "frontend", "front-end", "front end", "ai ", "artificial intelligence",
    "machine learning", "llm", "genai", "gen ai", "developer", "engineer"
]
# ===========================================================

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SEEN_FILE = "seen_jobs.json"


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen_ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen_ids), f)


def send_telegram(message):
    url = f"https://telegram.org{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=15)


def passes_location_rule(loc_text, title_text):
    combined = f"{loc_text} {title_text}".lower()
    # Lagos allows Onsite, Hybrid, and Remote
    if "lagos" in combined:
        return True
    # Outside Lagos: allow if Remote or Hybrid is mentioned
    if "remote" in combined or "hybrid" in combined:
        return True
    # Outside Lagos & explicitly marked On-site -> skip
    if "on-site" in combined or "onsite" in combined:
        return False
    # If location is simply "Nigeria" (often nationwide/remote), allow it
    if loc_text.strip().lower() == "nigeria":
        return True
    return False


def fetch_jobs():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    seen = load_seen()
    new_matches = 0

    for query in SEARCHES:
        url = (
            f"https://linkedin.com"
            f"?keywords={quote(query['keywords'])}"
            f"&location={quote(query['location'])}"
            f"&f_TPR=r{TIME_SECONDS}&start=0"
        )

        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code != 200:
                print(f"Skipping {query['keywords']}: status {resp.status_code}")
                continue
        except Exception as e:
            print(f"Request error for {query['keywords']}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        for card in soup.select("li"):
            base_card = card.select_one("div.base-card")
            if not base_card:
                continue

            urn = base_card.get("data-entity-urn", "")
            job_id = urn.split(":")[-1] if ":" in urn else ""
            if not job_id or job_id in seen:
                continue

            title_el = card.select_one("h3.base-search-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle")
            loc_el = card.select_one("span.job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")

            title = title_el.get_text(strip=True) if title_el else "Unknown Role"
            company = company_el.get_text(strip=True) if company_el else "Unknown Company"
            loc = loc_el.get_text(strip=True) if loc_el else query["location"]
            link = (
                link_el["href"].split("?")[0]
                if link_el and link_el.has_attr("href")
                else f"https://linkedin.com{job_id}"
            )

            # Mark as seen so we never alert twice
            seen.add(job_id)

            title_lower = f" {title.lower()} "

            # Filter out junior/intern/entry roles
            if any(bad in title_lower for bad in EXCLUDE_TITLE_WORDS):
                continue

            # Ensure title actually relates to your target engineering roles
            if not any(good in title_lower for good in INCLUDE_TITLE_WORDS):
                continue

            # Enforce Lagos (any) vs Other Nigerian States (Remote/Hybrid only)
            if not passes_location_rule(loc, title):
                continue

            msg = (
                f"🚨 <b>New Senior Engineering Role</b>\n\n"
                f"<b>Role:</b> {title}\n"
                f"<b>Company:</b> {company}\n"
                f"<b>Location:</b> {loc}\n"
                f"🔗 <a href='{link}'>View & Apply on LinkedIn</a>"
            )
            send_telegram(msg)
            new_matches += 1
            time.sleep(1)  # Gentle pause between Telegram messages

        time.sleep(2)  # Polite pause between LinkedIn search queries

    save_seen(seen)
    print(f"Done. Found {new_matches} new matching jobs.")


if __name__ == "__main__":
    fetch_jobs()
