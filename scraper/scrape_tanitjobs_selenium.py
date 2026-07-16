"""
Selenium-based scraper for Tanitjobs.com — use this if scrape_tanitjobs.py (requests-based)
gets a 403 Forbidden error. This drives an actual Chrome browser instead of sending raw
HTTP requests, which is much harder for anti-bot systems to detect and block.

SETUP (one-time):
    pip install selenium webdriver-manager
    (webdriver-manager auto-downloads the correct ChromeDriver for your installed Chrome
    version, so you don't need to manually download/manage it)

USAGE:
    python scrape_tanitjobs_selenium.py --pages 5

    Add --headless once you've confirmed it works, to run without opening a visible window:
    python scrape_tanitjobs_selenium.py --pages 5 --headless
"""

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "https://www.tanitjobs.com/categories/705/informatique-jobs/"
RATE_LIMIT_SECONDS = 3.0
PAGE_LOAD_TIMEOUT = 15

RAW_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Same confirmed selectors as the requests-based version
SELECTORS = {
    "job_card": "article.listing-item",
    "title": ".listing-item__title",
    "company": ".listing-item-info-company",
    "location": ".listing-item-info-location",
    "description": ".listing-item__desc",
}


def build_driver(headless: bool) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    # Further hide the fact this is an automated browser
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
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


def scrape(pages: int = 5, headless: bool = False) -> list[dict]:
    driver = build_driver(headless=headless)
    all_jobs = []

    try:
        for page_num in range(1, pages + 1):
            url = BASE_URL if page_num == 1 else f"{BASE_URL}?page={page_num}"
            print(f"Loading page {page_num}: {url}")
            driver.get(url)

            # Give the page a moment to load, then check if a CAPTCHA/challenge is showing.
            # If so, pause and let you solve it manually — the script will wait indefinitely
            # here instead of timing out while you're still clicking.
            time.sleep(2)
            page_text_lower = driver.page_source.lower()
            captcha_signals = ["captcha", "verify you are human", "checking your browser",
                                "cloudflare", "just a moment"]
            if any(signal in page_text_lower for signal in captcha_signals):
                print("  A CAPTCHA / verification challenge appears to be showing.")
                input("  Solve it in the browser window, then press Enter here to continue... ")
                time.sleep(1)

            try:
                WebDriverWait(driver, PAGE_LOAD_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["job_card"]))
                )
            except Exception:
                print(f"  No job cards appeared on page {page_num} within timeout.")
                print("  Possible causes: CAPTCHA shown, selector changed, or no more pages.")
                debug_dir = RAW_DATA_DIR.parent / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = debug_dir / f"debug_{ts}.png"
                html_path = debug_dir / f"debug_{ts}.html"
                driver.save_screenshot(str(screenshot_path))
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"  Saved a screenshot to: {screenshot_path}")
                print(f"  Saved the raw page HTML to: {html_path}")
                print("  Send Claude the screenshot so we can see what the browser actually loaded.")
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
    parser = argparse.ArgumentParser(description="Scrape IT job postings from Tanitjobs (Selenium)")
    parser.add_argument("--pages", type=int, default=5, help="Number of listing pages to scrape")
    parser.add_argument("--headless", action="store_true",
                         help="Run without opening a visible browser window")
    args = parser.parse_args()

    jobs = scrape(pages=args.pages, headless=args.headless)
    save_raw(jobs)
