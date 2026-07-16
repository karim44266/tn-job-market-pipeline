"""
Undetected-ChromeDriver scraper for Tanitjobs.com — use this if scrape_tanitjobs_selenium.py
gets stuck on Cloudflare's "Performing security verification" screen.

undetected-chromedriver is a patched Selenium driver specifically built to avoid the
fingerprinting checks Cloudflare (and similar services) use to detect automated browsers.
It's the standard tool for this exact situation.

SETUP (one-time):
    pip install undetected-chromedriver beautifulsoup4

USAGE:
    python scrape_tanitjobs_uc.py --pages 5

    Do NOT use headless mode with this approach — Cloudflare is more likely to flag
    headless browsers. Keep the window visible.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://www.tanitjobs.com/categories/705/informatique-jobs/"
RATE_LIMIT_SECONDS = 3.0
PAGE_LOAD_TIMEOUT = 25  # Cloudflare's JS challenge can take a few extra seconds to clear

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

SELECTORS = {
    "job_card": "article.listing-item",
    "title": ".listing-item__title",
    "company": ".listing-item-info-company",
    "location": ".listing-item-info-location",
    "description": ".listing-item__desc",
}


def build_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    driver = uc.Chrome(options=options, version_main=150)
    return driver


def parse_job_card(card_html: str) -> dict:
    card = BeautifulSoup(card_html, "html.parser")

    def safe_text(selector):
        el = card.select_one(selector)
        return el.get_text(strip=True) if el else None

    link_el = card.select_one("a")
    link = link_el["href"] if link_el and link_el.has_attr("href") else None
    if link and link.startswith("/"):
        link = "https://www.tanitjobs.com" + link

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
    driver = build_driver()
    all_jobs = []

    try:
        for page_num in range(1, pages + 1):
            url = BASE_URL if page_num == 1 else f"{BASE_URL}?page={page_num}"
            print(f"Loading page {page_num}: {url}")
            driver.get(url)

            # Give Cloudflare's automatic JS challenge time to clear on its own —
            # with undetected-chromedriver this usually resolves in a few seconds
            # without any manual click needed.
            time.sleep(4)

            try:
                WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["job_card"]))
                )
            except Exception:
                print(f"  No job cards appeared on page {page_num} within timeout.")
                debug_dir = RAW_DATA_DIR.parent / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = debug_dir / f"debug_uc_{ts}.png"
                html_path = debug_dir / f"debug_uc_{ts}.html"
                driver.save_screenshot(str(screenshot_path))
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"  Saved screenshot: {screenshot_path}")
                print(f"  Saved HTML: {html_path}")
                print("  If this still shows the Cloudflare page, wait longer (increase "
                      "PAGE_LOAD_TIMEOUT) or solve it manually in the window, then press Enter.")
                input("  Press Enter to try reading the page anyway (in case it loaded after)... ")
                cards_check = driver.find_elements(By.CSS_SELECTOR, SELECTORS["job_card"])
                if not cards_check:
                    break

            cards = driver.find_elements(By.CSS_SELECTOR, SELECTORS["job_card"])
            print(f"  Found {len(cards)} job cards")
            if not cards:
                break

            for card in cards:
                job = parse_job_card(card.get_attribute("outerHTML"))
                if job["title"]:
                    all_jobs.append(job)

            time.sleep(RATE_LIMIT_SECONDS)
    finally:
        driver.quit()

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
    parser = argparse.ArgumentParser(description="Scrape Tanitjobs using undetected-chromedriver")
    parser.add_argument("--pages", type=int, default=5, help="Number of listing pages to scrape")
    args = parser.parse_args()

    jobs = scrape(pages=args.pages)
    save_raw(jobs)
