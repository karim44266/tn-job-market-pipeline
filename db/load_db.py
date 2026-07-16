"""
Loads the processed CSVs into a SQLite database (data/processed/jobs.db).

Why SQLite to start: zero setup, one file, perfect for local development and for a
portfolio project a recruiter can run in 30 seconds. The schema below is written in
plain SQL so migrating to PostgreSQL later is a copy-paste job (see README for the
Postgres upgrade path) — worth doing once you want to deploy this somewhere real.

USAGE:
    python load_db.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
DB_PATH = PROCESSED_DIR / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    posting_id   TEXT PRIMARY KEY,
    title        TEXT,
    company      TEXT,
    location     TEXT,
    date_posted  TEXT,
    url          TEXT,
    source       TEXT,
    scraped_at   TEXT
);

CREATE TABLE IF NOT EXISTS posting_skills (
    posting_id TEXT,
    skill      TEXT,
    FOREIGN KEY (posting_id) REFERENCES postings(posting_id)
);

CREATE INDEX IF NOT EXISTS idx_posting_skills_skill ON posting_skills(skill);
CREATE INDEX IF NOT EXISTS idx_postings_location ON postings(location);
"""


def load():
    postings_df = pd.read_csv(PROCESSED_DIR / "postings.csv")
    skills_df = pd.read_csv(PROCESSED_DIR / "posting_skills.csv")

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    postings_df.to_sql("postings", conn, if_exists="replace", index=False)
    skills_df.to_sql("posting_skills", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print(f"Loaded {len(postings_df)} postings and {len(skills_df)} skill rows into {DB_PATH}")


if __name__ == "__main__":
    load()
