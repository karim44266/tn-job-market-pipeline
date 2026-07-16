"""
Streamlit dashboard for the Tunisia Tech Job Market pipeline.

USAGE:
    streamlit run app.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "jobs.db"

st.set_page_config(page_title="TN Tech Job Market", layout="wide")


@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)
    postings = pd.read_sql("SELECT * FROM postings", conn)
    skills = pd.read_sql("SELECT * FROM posting_skills", conn)
    conn.close()
    return postings, skills


st.title("🇹🇳 Tunisia Tech Job Market Dashboard")
st.caption("Built from live-scraped IT job postings — tracks skill demand, "
           "location distribution, and hiring companies over time.")

if not DB_PATH.exists():
    st.error(
        "No database found yet. Run the pipeline first:\n\n"
        "1. `python scraper/scrape_tanitjobs.py --pages 5`\n"
        "2. `python transform/transform_jobs.py`\n"
        "3. `python db/load_db.py`"
    )
    st.stop()

postings, skills = load_data()

col1, col2, col3 = st.columns(3)
col1.metric("Total postings", len(postings))
col2.metric("Unique companies", postings["company"].nunique())
col3.metric("Unique skills detected", skills["skill"].nunique())

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Most in-demand skills")
    top_skills = skills["skill"].value_counts().head(15).reset_index()
    top_skills.columns = ["skill", "count"]
    fig = px.bar(top_skills, x="count", y="skill", orientation="h")
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Postings by location")
    loc_counts = postings["location"].value_counts().head(10).reset_index()
    loc_counts.columns = ["location", "count"]
    fig2 = px.pie(loc_counts, names="location", values="count")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.subheader("Top hiring companies")
company_counts = postings["company"].value_counts().head(10).reset_index()
company_counts.columns = ["company", "postings"]
st.dataframe(company_counts, use_container_width=True)

st.divider()
st.subheader("Browse raw postings")
selected_skill = st.selectbox("Filter by skill", ["All"] + sorted(skills["skill"].unique().tolist()))
if selected_skill != "All":
    ids = skills[skills["skill"] == selected_skill]["posting_id"]
    filtered = postings[postings["posting_id"].isin(ids)]
else:
    filtered = postings
st.dataframe(filtered[["title", "company", "location", "date_posted", "url"]], use_container_width=True)
