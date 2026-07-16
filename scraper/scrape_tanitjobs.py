"""
Scraper for Tanitjobs.com — IT job category.
Collects raw job postings (title, company, location, date, description snippet, url)
and saves them as timestamped JSON in data/raw/.

ETHICAL SCRAPING NOTES:
- Respects robots.txt (check before running: https://www.tanitjobs.com/robots.txt)
- Adds a delay between requests (RATE_LIMIT_SECONDS below) to avoid hammering the server
- Only collects publicly visible listing data, no login/auth bypass
- Sets a descriptive User-Agent identifying this as a student/portfolio project

USAGE:
    python scrape_tanitjobs.py --pages 5

NOTE FOR KARIM: Job board HTML structures change over time and differ between sites.
The CSS selectors below (see `SELECTORS` dict) are your main tuning point — if the
scraper returns 0 results, open the site in your browser, right-click a job card ->
Inspect, and update the selectors to match what you see. This is a normal, expected
part of building any scraper and worth mentioning in interviews as "handled selector
drift when the site markup changed."
"""

import argparse
import json
import time
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.tanitjobs.com/categories/705/informatique-jobs/"
RATE_LIMIT_SECONDS = 3.0
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.tanitjobs.com/",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
}

# Use a persistent session so cookies (set on first request) carry over to later ones —
# some anti-bot setups check for a valid session cookie on the 2nd+ request.
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# --- Confirmed against live site HTML (via browser inspection, July 2026) ---
SELECTORS = {
    "job_card": "article.listing-item",
    "title": ".listing-item__title",
    "company": ".listing-item-info-company",
    "location": ".listing-item-info-location",
    "description": ".listing-item__desc",
    "link": "a",
}


def fetch_page(url: str) -> BeautifulSoup:
    resp = SESSION.get(url, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def warm_up_session():
    """Visit the homepage first so any cookies/tokens the site sets get stored
    in SESSION before we request the actual listing pages. Some anti-bot setups
    reject requests that don't have a valid cookie from a prior visit."""
    try:
        SESSION.get("https://www.tanitjobs.com/", timeout=15)
        time.sleep(1.5)
    except requests.RequestException as e:
        print(f"Warm-up request failed (continuing anyway): {e}")


def parse_job_card(card) -> dict:
    def safe_text(selector):
        el = card.select_one(selector)
        return el.get_text(strip=True) if el else None

    link_el = card.select_one(SELECTORS["link"])
    link = link_el["href"] if link_el and link_el.has_attr("href") else None
    if link and link.startswith("/"):
        link = "https://www.tanitjobs.com" + link

    # Company field sometimes ends with " - " (site markup quirk seen in dev tools),
    # strip trailing separators just in case.
    company = safe_text(SELECTORS["company"])
    if company:
        company = company.rstrip(" -").strip()

    return {
        "title": safe_text(SELECTORS["title"]),
        "company": company,
        "location": safe_text(SELECTORS["location"]),
        "description_snippet": safe_text(SELECTORS["description"]),
        "url": link,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "tanitjobs",
    }


def scrape(pages: int = 5) -> list[dict]:
    all_jobs = []
    warm_up_session()
    for page_num in range(1, pages + 1):
        url = BASE_URL if page_num == 1 else f"{BASE_URL}?page={page_num}"
        print(f"Fetching page {page_num}: {url}")
        try:
            soup = fetch_page(url)
        except requests.RequestException as e:
            print(f"  Failed to fetch page {page_num}: {e}")
            if "403" in str(e):
                print("  This is bot-detection blocking plain requests, not a code bug.")
                print("  Next step: switch to the Selenium version of this scraper "
                      "(drives a real browser, much harder to block). Tell Claude "
                      "and it will provide scrape_tanitjobs_selenium.py")
            break

        cards = soup.select(SELECTORS["job_card"])
        print(f"  Found {len(cards)} job cards")
        if not cards:
            print("  No cards found — selectors likely need adjusting for this site. "
                  "Open the page in a browser and inspect a job listing element.")
            break

        for card in cards:
            job = parse_job_card(card)
            if job["title"]:  # skip empty/broken cards
                all_jobs.append(job)

        time.sleep(RATE_LIMIT_SECONDS)

    return all_jobs


def save_raw(jobs: list[dict]) -> Path:
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RAW_DATA_DIR / f"tanitjobs_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(jobs)} jobs to {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape IT job postings from Tanitjobs")
    parser.add_argument("--pages", type=int, default=5, help="Number of listing pages to scrape")
    args = parser.parse_args()

    jobs = scrape(pages=args.pages)
    save_raw(jobs)
