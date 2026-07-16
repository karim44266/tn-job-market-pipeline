"""
Transformation layer.

Takes raw scraped JSON files from data/raw/, and produces two clean tables:
  1. data/processed/postings.csv      -> one row per job posting (deduplicated, cleaned)
  2. data/processed/posting_skills.csv -> one row per (posting_id, skill) pair (many-to-many)

This is the "data engineering" part of the project: normalizing messy scraped text
into structured tables ready for loading into a database.

USAGE:
    python transform_jobs.py
"""

import json
import re
from pathlib import Path
from hashlib import md5

import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

# Skill keyword list — extend this over time as you see what's actually in postings.
# Keys are the canonical skill name, values are regex patterns to match variants.
SKILL_PATTERNS = {
    "JavaScript": r"\bjavascript\b|\bjs\b",
    "TypeScript": r"\btypescript\b|\bts\b",
    "Python": r"\bpython\b",
    "Java": r"\bjava\b(?!script)",
    "PHP": r"\bphp\b",
    "SQL": r"\bsql\b",
    "React": r"\breact(\.js)?\b",
    "Angular": r"\bangular\b",
    "Vue": r"\bvue(\.js)?\b",
    "Node.js": r"\bnode(\.js)?\b",
    "NestJS": r"\bnest(\.?js)?\b",
    "Next.js": r"\bnext(\.?js)?\b",
    "Laravel": r"\blaravel\b",
    "Django": r"\bdjango\b",
    "Spring": r"\bspring\b",
    ".NET": r"\.net\b",
    "MongoDB": r"\bmongodb\b|\bmongo\b",
    "MySQL": r"\bmysql\b",
    "PostgreSQL": r"\bpostgres(ql)?\b",
    "Docker": r"\bdocker\b",
    "Kubernetes": r"\bkubernetes\b|\bk8s\b",
    "AWS": r"\baws\b",
    "Azure": r"\bazure\b",
    "GCP": r"\bgcp\b|\bgoogle cloud\b",
    "Git": r"\bgit\b",
    "WinDev": r"\bwindev\b",
    "Big Data": r"\bbig data\b|\bspark\b|\bhadoop\b",
    "Machine Learning": r"\bmachine learning\b|\bml\b|\bia\b|\bartificial intelligence\b",
}


def load_raw_jobs() -> list[dict]:
    jobs = []
    for file in RAW_DIR.glob("*.json"):
        with open(file, encoding="utf-8") as f:
            jobs.extend(json.load(f))
    return jobs


def make_posting_id(job: dict) -> str:
    # Stable ID based on url if present, else title+company, so re-scrapes dedupe correctly
    key = job.get("url") or f"{job.get('title')}|{job.get('company')}"
    return md5(key.encode("utf-8")).hexdigest()[:12]


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def extract_skills(text: str) -> list[str]:
    if not text:
        return []
    text_lower = text.lower()
    found = []
    for skill, pattern in SKILL_PATTERNS.items():
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


def transform() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_jobs = load_raw_jobs()
    print(f"Loaded {len(raw_jobs)} raw job records")

    postings_rows = []
    skills_rows = []
    seen_ids = set()

    for job in raw_jobs:
        posting_id = make_posting_id(job)
        if posting_id in seen_ids:
            continue  # dedupe across multiple scrape runs
        seen_ids.add(posting_id)

        title = clean_text(job.get("title"))
        company = clean_text(job.get("company"))
        location = clean_text(job.get("location"))
        description = clean_text(job.get("description_snippet"))

        postings_rows.append({
            "posting_id": posting_id,
            "title": title,
            "company": company,
            "location": location,
            "date_posted": job.get("date_posted"),
            "url": job.get("url"),
            "source": job.get("source"),
            "scraped_at": job.get("scraped_at"),
        })

        full_text = " ".join(filter(None, [title, description]))
        for skill in extract_skills(full_text):
            skills_rows.append({"posting_id": posting_id, "skill": skill})

    postings_df = pd.DataFrame(postings_rows)
    skills_df = pd.DataFrame(skills_rows)
    return postings_df, skills_df


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    postings_df, skills_df = transform()

    postings_out = PROCESSED_DIR / "postings.csv"
    skills_out = PROCESSED_DIR / "posting_skills.csv"
    postings_df.to_csv(postings_out, index=False)
    skills_df.to_csv(skills_out, index=False)

    print(f"Wrote {len(postings_df)} postings to {postings_out}")
    print(f"Wrote {len(skills_df)} posting-skill pairs to {skills_out}")
