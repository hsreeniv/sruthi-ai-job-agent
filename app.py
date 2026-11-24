from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from src.applications import (
    approve_application,
    list_applications_detailed,
    mark_application_submitted,
    prepare_application_package,
    reject_application,
    update_application_answers,
)
from src.autofill import launch_prefill_browser
from src.db import (
    dismiss_job,
    init_db,
    list_applications,
    list_company_directory,
    list_discovery_runs,
    list_jobs,
    save_job,
    update_job_analysis,
)
from src.discovery import discover_and_store, load_board_config, sync_company_directory
from src.eligibility import evaluate_job, sort_jobs_bengaluru_first
from src.gemini_service import analyze_job
from src.profile import load_profile
from src.resume import create_tailored_resume_with_ats
from src.sources.manual import import_jobs_csv

load_dotenv()
st.set_page_config(
    page_title="Sruthi AI Job Agent — NEO Command Center",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

# Modern Real-Time & NEO Command Center CSS
st.markdown(
    """
    <style>
    .stApp { background-color: #f1f5f9; }
    .block-container { padding-top: 1.1rem; padding-bottom: 2.5rem; max-width: 1420px; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }

    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
        70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
        100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
    }
    .live-dot {
        display: inline-block;
        width: 9px;
        height: 9px;
        background-color: #22c55e;
        border-radius: 50%;
        margin-right: 6px;
        animation: pulse 1.8s infinite;
    }

    /* Hero Banner */
    .hero-banner {
        background: linear-gradient(125deg, #0f172a 0%, #1e3a8a 55%, #2563eb 100%);
        color: #ffffff;
        padding: 20px 26px;
        border-radius: 14px;
        margin-bottom: 1rem;
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.14);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
    }
    .hero-left h1 { margin: 0 0 4px 0; color: #ffffff; font-size: 1.62rem; font-weight: 800; }
    .hero-left p { margin: 0; color: #dbeafe; font-size: 0.9rem; }
    .hero-badge {
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.25);
        padding: 8px 14px;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 600;
        color: #f8fafc;
    }

    /* Daily Goal Bar */
    .goal-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 5px solid #10b981;
        border-radius: 12px;
        padding: 14px 20px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
    }
    .goal-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.92rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 8px;
    }
    .goal-track {
        width: 100%;
        height: 10px;
        background: #e2e8f0;
        border-radius: 999px;
        overflow: hidden;
    }
    .goal-fill {
        height: 100%;
        background: linear-gradient(90deg, #10b981 0%, #2563eb 100%);
        border-radius: 999px;
    }

    /* NEO & Google Radar Cards */
    .radar-box {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-left: 5px solid #2563eb;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.06);
    }
    .neo-box {
        background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%);
        border: 1px solid #bfdbfe;
        border-left: 5px solid #7c3aed;
        border-radius: 12px;
        padding: 14px 18px;
        margin-bottom: 1rem;
    }

    /* Spotlight Cards */
    .spotlight-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 8px;
        box-shadow: 0 3px 10px rgba(15, 23, 42, 0.05);
        min-height: 190px;
    }
    .spotlight-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .spotlight-company { font-size: 0.88rem; font-weight: 700; color: #2563eb; }
    .score-badge {
        background: #0f172a;
        color: #ffffff;
        padding: 3px 9px;
        border-radius: 999px;
        font-size: 0.76rem;
        font-weight: 700;
    }
    .spotlight-title { font-size: 1.05rem; font-weight: 800; color: #0f172a; margin-bottom: 6px; line-height: 1.3; }
    .spotlight-meta { font-size: 0.82rem; color: #475569; margin-bottom: 8px; }
    .spotlight-reason {
        font-size: 0.78rem;
        color: #334155;
        background: #f8fafc;
        border-left: 3px solid #cbd5e1;
        padding: 6px 8px;
        border-radius: 4px;
        margin-bottom: 10px;
    }

    /* Pills */
    .pill {
        display: inline-block;
        padding: 3px 9px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 5px;
    }
    .pill-green { background: #dcfce7; color: #166534; }
    .pill-blue { background: #dbeafe; color: #1e40af; }
    .pill-amber { background: #fef3c7; color: #92400e; }
    .pill-purple { background: #f3e8ff; color: #6b21a8; }

    .panel-header {
        font-size: 1.12rem;
        font-weight: 800;
        color: #0f172a;
        margin: 0.3rem 0 0.7rem 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

profile = load_profile()

# Session state for clickable KPI navigation & filters
if "active_view" not in st.session_state:
    st.session_state["active_view"] = "📊 Live Dashboard"
if "pending_view" in st.session_state:
    st.session_state["active_view"] = st.session_state.pop("pending_view")
if "quick_mode" not in st.session_state:
    st.session_state["quick_mode"] = "All"
if "kpi_elig_override" not in st.session_state:
    st.session_state["kpi_elig_override"] = "All"
if "app_status_override" not in st.session_state:
    st.session_state["app_status_override"] = "All"


def _fetch_page_jd(url: str, fallback_snippet: str) -> str:
    """Fetches clean text from a job page to use as the JD, with snippet fallback."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code != 200:
            return fallback_snippet
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:3000] if len(text) > 120 else fallback_snippet
    except Exception:
        return fallback_snippet


def _search_and_ingest_in_app(query: str, profile_data: dict, max_results: int = 8) -> dict:
    """Fetches live job links + JDs directly inside Streamlit (no Google new tab)."""
    api_key = os.getenv("SERPER_API_KEY", "").strip()
    raw_results = []
    source_label = "Google Search (24h)"

    # 1. Try Serper.dev Google API if configured in Secrets
    if api_key:
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "gl": "in", "hl": "en", "tbs": "qdr:d", "num": max_results},
                timeout=15,
            )
            if resp.status_code == 200:
                for item in resp.json().get("organic", []):
                    raw_results.append(
                        {
                            "title": (item.get("title") or "").strip(),
                            "link": (item.get("link") or "").strip(),
                            "snippet": (item.get("snippet") or "").strip(),
                        }
                    )
        except Exception:
            pass

    # 2. Zero-key fallback: Live DuckDuckGo HTML search
    if not raw_results:
        source_label = "Live Web Search"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "df": "d"},
                headers=headers,
                timeout=12,
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            for res in soup.select(".result")[:max_results]:
                a_tag = res.select_one(".result__a")
                snip_tag = res.select_one(".result__snippet")
                if not a_tag:
                    continue
                href = a_tag.get("href", "")
                if "uddg=" in href:
                    href = unquote(parse_qs(urlparse(href).query).get("uddg", [href])[0])
                raw_results.append(
                    {
                        "title": a_tag.get_text(strip=True),
                        "link": href,
                        "snippet": snip_tag.get_text(strip=True) if snip_tag else "",
                    }
                )
        except Exception:
            pass

    inserted = 0
    for item in raw_results:
        title, link, snippet = item["title"], item["link"], item["snippet"]
        if not title or not link.startswith("http"):
            continue
        company = title.split("-")[0].split("|")[0].strip()[:60] or "Web Career"
        full_jd = _fetch_page_jd(link, f"{title}\n\n{snippet}")
        ev = evaluate_job(
            {"title": title, "location": "Bengaluru, Karnataka, India", "jd": full_jd},
            profile_data,
        )
        if ev["eligibility_status"] == "Excluded":
            continue
        res = save_job(
            title=title[:140],
            company=company,
            location="Bengaluru, Karnataka, India",
            url=link,
            source=source_label,
            jd=full_jd,
            track=ev["track"],
            match_score=ev["match_score"],
            eligibility_status=ev["eligibility_status"],
            eligibility_reasons=ev["eligibility_reasons"],
        )
        if res.get("status") == "inserted":
            inserted += 1

    return {"fetched": len(raw_results), "inserted": inserted, "source": source_label}


def _ingest_google_batch(profile_data: dict) -> dict:
    """Runs core Bengaluru 2027 web queries during full 24h discovery."""
    queries = [
        "ece freshers jobs in bangalore 2027 opening",
        "embedded systems intern bangalore 2027",
        "vlsi design verification intern bangalore 2027",
    ]
    total_fetched = 0
    total_inserted = 0
    for q in queries:
        r = _search_and_ingest_in_app(q, profile_data, max_results=5)
        total_fetched += r["fetched"]
        total_inserted += r["inserted"]
    return {"fetched": total_fetched, "inserted": total_inserted}


# ================= SIDEBAR =================
with st.sidebar:
    st.markdown("### 🎓 Candidate Profile")
    st.markdown(f"**{profile['name']}**")
    st.caption(f"{profile['degree']} • Batch {profile.get('batch', '2023-2027')}")
    st.caption(f"{profile.get('college', '')} ({profile.get('university', '')})")
    st.caption(
        f"Grad: {profile.get('graduation_month', 'May 2027')} • {profile.get('backlogs', 'No active backlogs')}"
    )
    st.divider()

    st.markdown("### 🤖 NEO Smart Mode")
    neo_auto_prep = st.toggle(
        "Auto-prepare 75%+ Bengaluru matches",
        value=False,
        help="Automatically generates tailored 1-page ATS PDF resumes & answers for top Bengaluru matches after discovery.",
    )
    daily_goal = st.number_input("Daily application goal", min_value=1, max_value=25, value=5, step=1)

    st.markdown("### 🔎 Live Filters")
    search_query = st.text_input("Search company or role", placeholder="e.g., Cisco, Qualcomm, Embedded")
    track_filter = st.selectbox("Engineering Track", ["All", "Core Engineering", "IT", "Other"])
    elig_filter = st.selectbox("Eligibility Tier", ["All", "Likely eligible", "Review required"])
    bengaluru_only = st.checkbox("Bengaluru priority only", value=False)
    min_score = st.slider("Minimum match score", 0, 100, 0, step=5)

    st.divider()
    target_cap = int(profile.get("daily_discovery_target", 100))
    if st.button(f"🚀 Run 24h Discovery ({target_cap} cap)", type="primary", width="stretch"):
        with st.spinner("Scanning 24h job boards + live web search & evaluating 2027 ECE eligibility..."):
            try:
                result = discover_and_store(profile, target_cap)
                g_res = _ingest_google_batch(profile)
                msg = result["summary"]
                if g_res["inserted"] > 0:
                    msg += f" | Web 24h: +{g_res['inserted']} new"
                if neo_auto_prep:
                    fresh_jobs = sort_jobs_bengaluru_first(list_jobs(include_applied=False))
                    existing_job_ids = {a.get("job_id") for a in list_applications()}
                    top_to_prep = [
                        j
                        for j in fresh_jobs
                        if j["id"] not in existing_job_ids
                        and int(j.get("match_score") or 0) >= 75
                        and j.get("eligibility_status") == "Likely eligible"
                    ][:3]
                    for j in top_to_prep:
                        prepare_application_package(j, profile)
                    if top_to_prep:
                        msg += f" | NEO auto-prepared {len(top_to_prep)} resume packages"
                st.success(msg)
                st.rerun()
            except Exception as e:
                st.error(f"Discovery failed: {e}")

    st.caption("🛡️ Final submission always requires Sruthi's explicit approval & manual click.")


def _apply_filters(job_list: list[dict], quick_mode: str = "All") -> list[dict]:
    out = sort_jobs_bengaluru_first(job_list)
    if search_query.strip():
        q = search_query.strip().lower()
        out = [
            j
            for j in out
            if q in (j.get("company") or "").lower() or q in (j.get("title") or "").lower()
        ]
    if track_filter != "All":
        out = [j for j in out if j.get("track") == track_filter]

    effective_elig = (
        st.session_state.get("kpi_elig_override", "All")
        if elig_filter == "All"
        else elig_filter
    )
    if effective_elig != "All":
        out = [j for j in out if j.get("eligibility_status") == effective_elig]

    if bengaluru_only or quick_mode == "🔥 Bengaluru Only":
        out = [
            j
            for j in out
            if "bengaluru" in (j.get("location") or "").lower()
            or "bangalore" in (j.get("location") or "").lower()
        ]
    if quick_mode == "🔎 Google / Web":
        out = [
            j
            for j in out
            if "google" in (j.get("source") or "").lower()
            or "web" in (j.get("source") or "").lower()
        ]
    elif quick_mode == "⚡ Core ECE":
        out = [j for j in out if j.get("track") == "Core Engineering"]
    elif quick_mode == "💻 IT / Software":
        out = [j for j in out if j.get("track") == "IT"]
    elif quick_mode == "⭐ Score 70+":
        out = [j for j in out if int(j.get("match_score") or 0) >= 70]
    if min_score > 0:
        out = [j for j in out if int(j.get("match_score") or 0) >= min_score]
    return out


# Load live data (applied & dismissed jobs automatically excluded)
active_jobs = list_jobs(include_applied=False)
apps = list_applications()
apps_detailed = list_applications_detailed()
runs = list_discovery_runs(limit=5)

last_sync = runs[0].get("run_at", "")[:16].replace("T", " ") + " UTC" if runs else "Ready to sync"
today_str = datetime.now().strftime("%Y-%m-%d")
submitted_today = sum(
    1 for a in apps if a.get("status") == "submitted" and str(a.get("submitted_at") or "").startswith(today_str)
)
submitted_total = sum(1 for a in apps if a.get("status") == "submitted")
goal_progress_count = max(submitted_today, 0)
goal_pct = min(100, int((goal_progress_count / max(1, daily_goal)) * 100))

# ================= HERO BANNER =================
st.markdown(
    f"""
    <div class="hero-banner">
      <div class="hero-left">
        <h1>🎯 Sruthi AI Job Agent — NEO Command Center</h1>
        <p>In-App 24h Web & Board Discovery • 2027 B.Tech ECE Guardrail • 1-Click Tailored ATS PDF Resumes</p>
      </div>
      <div class="hero-badge">
        <span class="live-dot"></span>LIVE &nbsp;|&nbsp; Last Sync: {last_sync}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ================= DAILY MOMENTUM BAR =================
motivation_msg = (
    "🔥 Daily target crushed!"
    if goal_progress_count >= daily_goal
    else f"🚀 {daily_goal - goal_progress_count} more application(s) to hit today's target!"
)
st.markdown(
    f"""
    <div class="goal-card">
      <div class="goal-header">
        <span>⚡ Today's Application Momentum: {goal_progress_count} / {daily_goal} Submitted ({goal_pct}%)</span>
        <span style="color:#2563eb;font-size:0.85rem;">{motivation_msg}</span>
      </div>
      <div class="goal-track">
        <div class="goal-fill" style="width: {goal_pct}%;"></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ================= CLICKABLE TOP KPI STRIP =================
likely_count = sum(1 for j in active_jobs if j.get("eligibility_status") == "Likely eligible")
blr_count = sum(
    1
    for j in active_jobs
    if "bengaluru" in (j.get("location") or "").lower()
    or "bangalore" in (j.get("location") or "").lower()
)
awaiting_count = sum(1 for a in apps if a.get("status") in ("awaiting_approval", "approved"))

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    if st.button(f"Active Unapplied\n\n**{len(active_jobs)}**", key="kpi_all", width="stretch"):
        st.session_state["active_view"] = "📊 Live Dashboard"
        st.session_state["quick_mode"] = "All"
        st.session_state["kpi_elig_override"] = "All"
        st.rerun()
with k2:
    if st.button(f"Likely Eligible\n\n**{likely_count}**", key="kpi_elig", width="stretch"):
        st.session_state["active_view"] = "📊 Live Dashboard"
        st.session_state["quick_mode"] = "All"
        st.session_state["kpi_elig_override"] = "Likely eligible"
        st.rerun()
with k3:
    if st.button(f"Bengaluru Priority\n\n**{blr_count}**", key="kpi_blr", width="stretch"):
        st.session_state["active_view"] = "📊 Live Dashboard"
        st.session_state["quick_mode"] = "🔥 Bengaluru Only"
        st.session_state["kpi_elig_override"] = "All"
        st.rerun()
with k4:
    if st.button(f"NEO Ready Queue\n\n**{awaiting_count}**", key="kpi_neo", width="stretch"):
        st.session_state["active_view"] = "⚡ NEO 1-Tap Queue"
        st.rerun()
with k5:
    if st.button(f"Total Submitted\n\n**{submitted_total}**", key="kpi_sub", width="stretch"):
        st.session_state["active_view"] = "📋 All Applications"
        st.session_state["app_status_override"] = "submitted"
        st.rerun()

st.write("")

# Navigation bar (synced with clickable KPIs)
views = [
    "📊 Live Dashboard",
    "⚡ NEO 1-Tap Queue",
    "🔍 Discover & Manual",
    "📋 All Applications",
    "🏢 Company Directory",
    "👤 Profile",
]
active_view = st.segmented_control(
    "Navigation",
    views,
    key="active_view",
    label_visibility="collapsed",
) or "📊 Live Dashboard"

# ================= VIEW 1: LIVE DASHBOARD =================
if active_view == "📊 Live Dashboard":
    st.markdown(
        """
        <div class="radar-box">
          <strong>🔎 In-App Live 24h Job Radar (Bengaluru • 2027 ECE &amp; Freshers)</strong><br>
          <span style="font-size:0.84rem;color:#475569;">Tap any pill or enter a query below to fetch live job links &amp; JDs directly into your dashboard (no new Google tab):</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    g_presets = [
        ("📡 ECE Freshers 2027 BLR", "ece freshers jobs in bangalore 2027 opening"),
        ("🔌 Embedded / Firmware Intern", "embedded systems firmware intern bangalore 2027"),
        ("🔬 VLSI / RTL Design Intern", "vlsi rtl design verification intern bangalore 2027"),
        ("🌐 Cisco / Qualcomm / TI", "Cisco OR Qualcomm OR Texas Instruments intern bangalore 2027"),
        ("💻 Junior Software / Python", "junior software engineer python intern bangalore 2027"),
    ]
    g_cols = st.columns(len(g_presets))
    for idx, (label, q_str) in enumerate(g_presets):
        with g_cols[idx]:
            if st.button(label, key=f"inapp_g_{idx}", width="stretch"):
                with st.spinner(f"Fetching live links & JDs for '{q_str}'..."):
                    res = _search_and_ingest_in_app(q_str, profile)
                    st.session_state["quick_mode"] = "🔎 Google / Web"
                    st.session_state["kpi_elig_override"] = "All"
                    st.success(f"Fetched {res['fetched']} results ({res['inserted']} new jobs added to your feed!).")
                    st.rerun()

    gs1, gs2 = st.columns([4, 1.3])
    with gs1:
        custom_google_q = st.text_input(
            "Custom 24h job search",
            value="ece freshers jobs in bangalore 2027 opening",
            label_visibility="collapsed",
            placeholder="Type any job query to fetch links & JDs directly into the app...",
        )
    with gs2:
        if st.button("🔎 Fetch Jobs (In-App)", type="primary", width="stretch"):
            q_run = custom_google_q.strip() or "ece freshers jobs in bangalore 2027 opening"
            with st.spinner(f"Fetching live links & JDs for '{q_run}'..."):
                res = _search_and_ingest_in_app(q_run, profile)
                st.session_state["quick_mode"] = "🔎 Google / Web"
                st.session_state["kpi_elig_override"] = "All"
                st.success(f"Fetched {res['fetched']} results ({res['inserted']} new jobs added to your feed!).")
                st.rerun()

    st.divider()

    # Quick-filter bar + NEO Auto-Prepare Action
    qf_col, neo_btn_col = st.columns([3.7, 1.3])
    with qf_col:
        quick_mode = st.segmented_control(
            "Quick Focus",
            ["All", "🔎 Google / Web", "🔥 Bengaluru Only", "⚡ Core ECE", "💻 IT / Software", "⭐ Score 70+"],
            key="quick_mode",
            label_visibility="collapsed",
        ) or "All"
    with neo_btn_col:
        if st.button("⚡ NEO Auto-Prepare Top 3", type="primary", width="stretch"):
            candidates = _apply_filters(active_jobs, quick_mode=quick_mode)
            existing_ids = {a.get("job_id") for a in apps}
            unprepped = [j for j in candidates if j["id"] not in existing_ids][:3]
            if not unprepped:
                st.info("Top matching jobs are already prepared in your NEO 1-Tap Queue!")
            else:
                with st.spinner(f"NEO AI is tailoring {len(unprepped)} 1-page ATS PDF resumes..."):
                    for j in unprepped:
                        prepare_application_package(j, profile)
                    st.session_state["pending_view"] = "⚡ NEO 1-Tap Queue"
                    st.rerun()

    filtered_jobs = _apply_filters(active_jobs, quick_mode=quick_mode)

    # 1. Spotlight: Top 3 Priority Matches
    active_elig_badge = (
        f" • Filtered: {st.session_state['kpi_elig_override']}"
        if st.session_state.get("kpi_elig_override", "All") != "All"
        else ""
    )
    st.markdown(
        f'<div class="panel-header">🔥 Top Priority Matches to Apply Right Now ({len(filtered_jobs)} ready{active_elig_badge})</div>',
        unsafe_allow_html=True,
    )
    if filtered_jobs:
        top3 = filtered_jobs[:3]
        cols = st.columns(len(top3))
        for idx, job in enumerate(top3):
            with cols[idx]:
                elig = job.get("eligibility_status", "Review required")
                pill_cls = "pill-green" if elig == "Likely eligible" else "pill-amber"
                score_val = int(job.get("match_score") or 0)
                try:
                    reasons = json.loads(job.get("eligibility_reasons") or "[]")
                    reason_txt = reasons[0] if reasons else "Matched 2027 India engineering criteria."
                except Exception:
                    reason_txt = "Matched 2027 India engineering criteria."

                st.markdown(
                    f"""
                    <div class="spotlight-card">
                      <div class="spotlight-top">
                        <span class="spotlight-company">{job.get('company', '')[:32]}</span>
                        <span class="score-badge">Match {score_val}%</span>
                      </div>
                      <div class="spotlight-title">{job.get('title', '')[:60]}</div>
                      <div class="spotlight-meta">📍 {job.get('location', 'India')} &nbsp;•&nbsp; {job.get('source', '')}</div>
                      <div class="spotlight-reason">{reason_txt[:95]}</div>
                      <div>
                        <span class="pill {pill_cls}">{elig}</span>
                        <span class="pill pill-blue">{job.get('track', 'Other')}</span>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                b1, b2, b3 = st.columns([1.2, 1.1, 0.9])
                with b1:
                    if st.button("📄 Prepare", key=f"dash_prep_{job['id']}", type="primary", width="stretch"):
                        with st.spinner("Tailoring PDF resume & checking ATS score..."):
                            try:
                                pkg = prepare_application_package(job, profile)
                                st.success(f"Ready in NEO Queue (#{pkg['application_id']})!")
                            except Exception as e:
                                st.error(str(e))
                with b2:
                    if job.get("url"):
                        st.link_button("🔗 Apply", job["url"], width="stretch")
                with b3:
                    if st.button("🙈 Hide", key=f"dash_hide_{job['id']}", width="stretch"):
                        dismiss_job(job["id"], reason_status="dismissed")
                        st.rerun()
    else:
        st.info("No active jobs match this filter. Click 'Active Unapplied' above or run a fresh search.")

    st.divider()

    # 2. Analytics Charts
    st.markdown('<div class="panel-header">📈 Live Discovery Breakdown</div>', unsafe_allow_html=True)
    if active_jobs:
        ch1, ch2 = st.columns(2)
        with ch1:
            st.caption("Active Jobs by Engineering Track")
            track_counts = Counter(j.get("track") or "Other" for j in active_jobs)
            df_track = pd.DataFrame(
                {"Track": list(track_counts.keys()), "Jobs": list(track_counts.values())}
            ).set_index("Track")
            st.bar_chart(df_track, color="#2563eb", height=210)
        with ch2:
            st.caption("Active Jobs by Source")
            source_counts = Counter(j.get("source") or "Unknown" for j in active_jobs)
            df_src = pd.DataFrame(
                {"Source": list(source_counts.keys()), "Jobs": list(source_counts.values())}
            ).set_index("Source")
            st.bar_chart(df_src, color="#10b981", height=210)

    st.divider()

    # 3. Full Interactive Table + CSV Export
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown(
            f'<div class="panel-header">📋 All Matching Opportunities ({len(filtered_jobs)})</div>',
            unsafe_allow_html=True,
        )
    if filtered_jobs:
        table_rows = [
            {
                "Score": int(j.get("match_score") or 0),
                "Company": j.get("company", ""),
                "Role": j.get("title", ""),
                "Location": j.get("location", ""),
                "Track": j.get("track", ""),
                "Eligibility": j.get("eligibility_status", ""),
                "Source": j.get("source", ""),
                "Date": j.get("discovery_date", ""),
                "Apply Link": j.get("url") or None,
            }
            for j in filtered_jobs[:100]
        ]
        with head_r:
            csv_bytes = pd.DataFrame(table_rows).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV",
                data=csv_bytes,
                file_name="sruthi_opportunities.csv",
                mime="text/csv",
                width="stretch",
            )
        st.dataframe(
            table_rows,
            width="stretch",
            hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn("Match Score", min_value=0, max_value=100, format="%d%%"),
                "Apply Link": st.column_config.LinkColumn("Job URL", display_text="Open"),
            },
        )

# ================= VIEW 2: NEO 1-TAP MOBILE QUEUE =================
elif active_view == "⚡ NEO 1-Tap Queue":
    st.markdown(
        """
        <div class="neo-box">
          <strong>⚡ NEO 1-Tap Mobile Application Deck</strong><br>
          <span style="font-size:0.86rem;color:#334155;">Each card below already has a tailored 1-page ATS PDF resume &amp; screening answers ready. On mobile: <b>1. Download Resume → 2. Tap Open &amp; Apply → 3. Mark Submitted</b>.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    ready_queue = [a for a in apps_detailed if a.get("status") in ("awaiting_approval", "approved")]
    if not ready_queue:
        st.info("No tailored packages in the queue yet. Click '⚡ NEO Auto-Prepare Top 3' on the Live Dashboard!")
    else:
        for app_row in ready_queue:
            app_id = app_row["id"]
            status = app_row.get("status", "awaiting_approval")
            try:
                ans_data = json.loads(app_row.get("answers_json") or "{}")
            except Exception:
                ans_data = {"answers": []}
            ats_rep = ans_data.get("ats_report") or {}
            ats_score = ats_rep.get("ats_score", "N/A")

            with st.container(border=True):
                c_info, c_badges = st.columns([3, 1.2])
                with c_info:
                    st.markdown(f"### {app_row['company']} — {app_row['title']}")
                    st.caption(
                        f"📍 {app_row.get('location') or 'Bengaluru, India'} • "
                        f"Match: {app_row.get('match_score')}% • ATS Score: {ats_score}/100"
                    )
                with c_badges:
                    st.markdown(
                        f"<div style='text-align:right;'><span class='pill pill-purple'>{status.upper()}</span></div>",
                        unsafe_allow_html=True,
                    )

                resume_file = Path(app_row.get("resume_path") or "")
                m1, m2, m3, m4 = st.columns([1.3, 1.2, 1.2, 0.9])
                with m1:
                    if resume_file.exists():
                        mime = (
                            "application/pdf"
                            if resume_file.suffix.lower() == ".pdf"
                            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                        with open(resume_file, "rb") as f:
                            st.download_button(
                                "⬇️ 1. Tailored Resume",
                                f,
                                file_name=resume_file.name,
                                mime=mime,
                                key=f"neo_dl_{app_id}",
                                width="stretch",
                            )
                with m2:
                    if app_row.get("url"):
                        st.link_button("🔗 2. Open & Apply", app_row["url"], type="primary", width="stretch")
                with m3:
                    if st.button("✔️ 3. Mark Submitted", key=f"neo_sub_{app_id}", width="stretch"):
                        if status == "awaiting_approval":
                            approve_application(app_id)
                        mark_application_submitted(app_id)
                        st.success("Submitted & removed from active feed!")
                        st.rerun()
                with m4:
                    if st.button("🗑️ Skip", key=f"neo_rej_{app_id}", width="stretch"):
                        reject_application(app_id)
                        st.rerun()

                if ans_data.get("answers"):
                    with st.expander("📝 Copy-Ready Screening Answers"):
                        for idx, item in enumerate(ans_data["answers"]):
                            st.markdown(f"**Q{idx + 1}: {item.get('question', '')}**")
                            st.code(item.get("draft_answer", ""), language=None)

# ================= VIEW 3: DISCOVER & MANUAL =================
elif active_view == "🔍 Discover & Manual":
    filtered_feed = _apply_filters(active_jobs)
    st.subheader("Active Job Feed & Manual Entry")
    st.caption("Already-applied and hidden jobs are permanently excluded from this feed and future daily runs.")

    c_add, c_csv = st.columns(2)
    with c_add:
        with st.expander("➕ Paste a job found on Google / LinkedIn / Naukri"):
            with st.form("add_job"):
                title = st.text_input("Job title")
                company = st.text_input("Company")
                location = st.text_input("Location", value="Bengaluru, India")
                url = st.text_input("Job URL")
                source = st.selectbox(
                    "Source",
                    ["Google Search", "Company careers", "LinkedIn", "Indeed", "Naukri", "Greenhouse", "Lever", "Manual"],
                )
                jd = st.text_area("Full job description", height=160)
                if st.form_submit_button("Evaluate & Save Job"):
                    if not title or not company or not jd:
                        st.error("Please provide job title, company, and job description.")
                    else:
                        ev = evaluate_job({"title": title, "location": location, "jd": jd}, profile)
                        res = save_job(
                            title=title,
                            company=company,
                            location=location,
                            url=url,
                            source=source,
                            jd=jd,
                            track=ev["track"],
                            match_score=ev["match_score"],
                            eligibility_status=ev["eligibility_status"],
                            eligibility_reasons=ev["eligibility_reasons"],
                        )
                        if res["status"] == "inserted":
                            st.success(f"Saved ({ev['eligibility_status']} | Score: {ev['match_score']}).")
                            st.rerun()
                        else:
                            st.info("Duplicate job detected; updated last_seen_at.")
    with c_csv:
        with st.expander("📥 Import jobs from CSV"):
            st.caption("Columns: title, company, location, url, source, jd")
            uploaded = st.file_uploader("Choose CSV", type=["csv"])
            if uploaded and st.button("Import CSV"):
                count = import_jobs_csv(uploaded)
                st.success(f"Processed {count} CSV rows.")
                st.rerun()

    st.divider()
    st.markdown(f"#### Unapplied Jobs ({len(filtered_feed)})")
    if not filtered_feed:
        st.info("No active jobs match your filters.")
    else:
        for job in filtered_feed[:40]:
            elig = job.get("eligibility_status", "Review required")
            icon = "🟢" if elig == "Likely eligible" else "🟡"
            header = f"{icon} [{job.get('match_score', 0)}%] {job['company']} — {job['title']} ({job.get('location', 'India')})"
            with st.expander(header):
                st.write(
                    f"**Track:** {job.get('track', 'Other')} | "
                    f"**Eligibility:** {elig} | "
                    f"**Source:** {job.get('source', '')} | "
                    f"**Found:** {job.get('discovery_date', '')}"
                )
                if job.get("url"):
                    st.markdown(f"**Job Link:** [{job['url']}]({job['url']})")
                try:
                    reasons = json.loads(job.get("eligibility_reasons") or "[]")
                except Exception:
                    reasons = []
                if reasons:
                    st.caption(" • ".join(reasons))
                st.write((job.get("jd") or "")[:1200])

                b1, b2, b3 = st.columns([1.2, 1.5, 1.2])
                with b1:
                    if st.button("🤖 Analyze with Gemini", key=f"analyze_{job['id']}", width="stretch"):
                        with st.spinner("Analyzing JD with Gemini..."):
                            try:
                                analysis = analyze_job(job, profile)
                                st.session_state[f"analysis_{job['id']}"] = analysis
                                update_job_analysis(
                                    job_id=job["id"],
                                    match_score=analysis.get("match_score"),
                                    track=analysis.get("track"),
                                    eligibility_status=analysis.get("eligibility_status"),
                                    eligibility_reasons=analysis.get("eligibility_reasons"),
                                )
                            except Exception as e:
                                st.error(str(e))
                with b2:
                    if st.button("📄 Prepare Application Package", key=f"prep_{job['id']}", type="primary", width="stretch"):
                        with st.spinner("Generating tailored PDF resume, ATS score & screening answers..."):
                            try:
                                analysis = st.session_state.get(f"analysis_{job['id']}")
                                pkg = prepare_application_package(job, profile, analysis=analysis)
                                ats_val = (pkg.get("ats_report") or {}).get("ats_score", "N/A")
                                st.success(
                                    f"Queued Application #{pkg['application_id']} (ATS Score: {ats_val}/100). "
                                    "Open '⚡ NEO 1-Tap Queue' or '📋 All Applications'."
                                )
                            except Exception as e:
                                st.error(f"Preparation failed: {e}")
                with b3:
                    if st.button("🙈 Hide / Already Applied", key=f"hide_{job['id']}", width="stretch"):
                        dismiss_job(job["id"], reason_status="dismissed")
                        st.rerun()

                analysis = st.session_state.get(f"analysis_{job['id']}")
                if analysis:
                    st.json(analysis)
                    if st.button("Generate tailored PDF resume + ATS score", key=f"resume_{job['id']}"):
                        path, ats = create_tailored_resume_with_ats(profile, analysis, job)
                        resume_p = Path(path)
                        mime = (
                            "application/pdf"
                            if resume_p.suffix.lower() == ".pdf"
                            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                        st.success(f"Resume created: {resume_p.name} | ATS Score: {ats['ats_score']}/100 ({ats['grade']})")
                        with open(resume_p, "rb") as f:
                            st.download_button(
                                f"⬇️ Download Tailored Resume ({resume_p.suffix.upper().lstrip('.')})",
                                f,
                                file_name=resume_p.name,
                                mime=mime,
                                key=f"download_{job['id']}",
                            )

# ================= VIEW 4: ALL APPLICATIONS =================
elif active_view == "📋 All Applications":
    st.subheader("Full Application History & Desktop Autofill")
    st.caption(
        "Use '⚡ NEO 1-Tap Queue' on mobile, or use desktop Playwright prefill below when running on your laptop."
    )

    status_options = ["All", "awaiting_approval", "approved", "submitted", "rejected"]
    default_idx = status_options.index(st.session_state.get("app_status_override", "All"))
    status_filter = st.selectbox("Filter by status", status_options, index=default_idx)
    st.session_state["app_status_override"] = status_filter

    filtered_apps = (
        apps_detailed
        if status_filter == "All"
        else [a for a in apps_detailed if a.get("status") == status_filter]
    )

    if not filtered_apps:
        st.info("No applications in this status.")
    else:
        for app_row in filtered_apps:
            app_id = app_row["id"]
            status = app_row.get("status", "awaiting_approval")
            header = (
                f"#{app_id} | {app_row['company']} — {app_row['title']} "
                f"[{status.upper()} | Match: {app_row.get('match_score')}%]"
            )
            with st.expander(header, expanded=(status in ("awaiting_approval", "approved"))):
                st.write(
                    f"**Location:** {app_row.get('location') or 'Not specified'} | "
                    f"**Eligibility:** {app_row.get('eligibility_status')} | "
                    f"**Source:** {app_row.get('source')}"
                )
                if app_row.get("url"):
                    st.markdown(f"**Job URL:** [{app_row['url']}]({app_row['url']})")

                try:
                    ans_data = json.loads(app_row.get("answers_json") or "{}")
                except Exception:
                    ans_data = {"answers": []}

                ats_rep = ans_data.get("ats_report")
                if ats_rep:
                    a1, a2, a3 = st.columns(3)
                    a1.metric("ATS Score", f"{ats_rep['ats_score']}/100", ats_rep.get("grade", ""))
                    a2.metric("Keyword Match", f"{ats_rep.get('keyword_match_pct', 0)}%")
                    a3.metric("Word Count", ats_rep.get("word_count", 0))
                    st.write(f"**Matched JD Keywords:** {', '.join(ats_rep.get('matched_keywords', [])) or 'None'}")
                    if ats_rep.get("missing_keywords"):
                        st.warning(f"**Missing JD Keywords (not fabricated):** {', '.join(ats_rep['missing_keywords'])}")

                resume_file = Path(app_row.get("resume_path") or "")
                if resume_file.exists():
                    mime = (
                        "application/pdf"
                        if resume_file.suffix.lower() == ".pdf"
                        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                    with open(resume_file, "rb") as f:
                        st.download_button(
                            f"⬇️ Download Tailored Resume ({resume_file.name})",
                            f,
                            file_name=resume_file.name,
                            mime=mime,
                            key=f"app_dl_{app_id}",
                        )

                answers_list = ans_data.get("answers", [])
                if answers_list:
                    st.write("**Screening answers (review & edit before approving):**")
                    updated_answers = []
                    for idx, item in enumerate(answers_list):
                        q_text = item.get("question", f"Question {idx + 1}")
                        draft = item.get("draft_answer", "")
                        needs_ver = item.get("needs_verification", False)
                        label = f"Q{idx + 1}: {q_text}" + (" [VERIFY]" if needs_ver else "")
                        edited = st.text_area(label, value=draft, key=f"ans_{app_id}_{idx}", height=75)
                        updated_answers.append(
                            {
                                "question": q_text,
                                "draft_answer": edited,
                                "needs_verification": "[VERIFY" in edited,
                            }
                        )
                    if st.button("Save edited answers", key=f"save_ans_{app_id}"):
                        ans_data["answers"] = updated_answers
                        update_application_answers(app_id, ans_data)
                        st.success("Screening answers saved.")

                st.divider()

                if status == "awaiting_approval":
                    c_ok, c_no = st.columns(2)
                    with c_ok:
                        if st.button("✅ Approve Application (Sruthi's OK)", key=f"approve_{app_id}", type="primary", width="stretch"):
                            approve_application(app_id)
                            st.rerun()
                    with c_no:
                        if st.button("❌ Reject", key=f"reject_{app_id}", width="stretch"):
                            reject_application(app_id)
                            st.rerun()

                elif status == "approved":
                    st.success(f"Approved at {app_row.get('approved_at')}. Ready for submission.")
                    c_auto, c_sub = st.columns(2)
                    with c_auto:
                        if st.button("🌐 Launch Desktop Autofill (Laptop Only)", key=f"autofill_{app_id}", width="stretch"):
                            try:
                                res = launch_prefill_browser(
                                    job_url=app_row.get("url") or "",
                                    profile=profile,
                                    resume_path=str(resume_file),
                                )
                                st.info(
                                    f"Prefilled fields: {', '.join(res['filled_fields']) or 'None'}. "
                                    "Click 'Mark as Submitted' once you finish submitting."
                                )
                            except Exception as e:
                                st.error(str(e))
                    with c_sub:
                        if st.button("✔️ Mark as Submitted", key=f"submit_{app_id}", type="primary", width="stretch"):
                            try:
                                mark_application_submitted(app_id)
                                st.success("Marked as submitted and removed from active discovery feed!")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))

                elif status == "submitted":
                    st.success(f"Submitted at {app_row.get('submitted_at')}.")
                elif status == "rejected":
                    st.info("Application was rejected.")

# ================= VIEW 5: COMPANY DIRECTORY =================
elif active_view == "🏢 Company Directory":
    st.subheader("Employer Source Directory")
    if st.button("Sync directory from config/boards.json"):
        count = sync_company_directory(load_board_config())
        st.success(f"Synced {count} companies into SQLite.")
    directory = list_company_directory()
    if not directory:
        sync_company_directory(load_board_config())
        directory = list_company_directory()
    dir_cols = [
        "company_name",
        "ats_provider",
        "board_identifier",
        "category",
        "location",
        "connector_status",
        "enabled",
        "last_successful_fetch",
        "last_error",
        "career_url",
    ]
    st.dataframe([{k: d.get(k) for k in dir_cols} for d in directory], width="stretch", hide_index=True)

# ================= VIEW 6: PROFILE =================
elif active_view == "👤 Profile":
    st.subheader("Verified Candidate Profile")
    st.caption("Edit `data/profile.json` to maintain the verified master profile. No unverified facts are ever fabricated.")
    st.json(profile)