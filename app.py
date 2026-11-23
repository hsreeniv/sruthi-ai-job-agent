from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
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
    page_title="Sruthi AI Job Agent",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_db()

# Modern Real-Time Command Center CSS
st.markdown(
    """
    <style>
    .stApp { background-color: #f1f5f9; }
    .block-container { padding-top: 1.1rem; padding-bottom: 2.5rem; max-width: 1420px; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }

    /* Pulsing Live Dot */
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
    .hero-left h1 { margin: 0 0 4px 0; color: #ffffff; font-size: 1.65rem; font-weight: 800; }
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

    /* KPI Metric Cards */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-top: 4px solid #2563eb;
        border-radius: 12px;
        padding: 14px 16px;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
    }
    div[data-testid="stMetricLabel"] { font-size: 0.82rem; font-weight: 600; color: #64748b; }
    div[data-testid="stMetricValue"] { font-size: 1.95rem; font-weight: 800; color: #0f172a; }

    /* Spotlight Cards */
    .spotlight-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 8px;
        box-shadow: 0 3px 10px rgba(15, 23, 42, 0.05);
        min-height: 185px;
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

    st.markdown("### 🎯 Daily Goal")
    daily_goal = st.number_input("Applications / day target", min_value=1, max_value=25, value=5, step=1)

    st.markdown("### 🔎 Live Filters")
    search_query = st.text_input("Search company or role", placeholder="e.g., Qualcomm, Embedded, Python")
    track_filter = st.selectbox("Engineering Track", ["All", "Core Engineering", "IT", "Other"])
    elig_filter = st.selectbox("Eligibility Tier", ["All", "Likely eligible", "Review required"])
    bengaluru_only = st.checkbox("Bengaluru priority only", value=False)
    min_score = st.slider("Minimum match score", 0, 100, 0, step=5)

    st.divider()
    target_cap = int(profile.get("daily_discovery_target", 100))
    if st.button(f"🚀 Run 24h Discovery ({target_cap} cap)", type="primary", width="stretch"):
        with st.spinner("Fetching 24h job boards and evaluating 2027 ECE eligibility..."):
            try:
                result = discover_and_store(profile, target_cap)
                st.success(result["summary"])
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
    if elig_filter != "All":
        out = [j for j in out if j.get("eligibility_status") == elig_filter]
    if bengaluru_only or quick_mode == "🔥 Bengaluru Only":
        out = [
            j
            for j in out
            if "bengaluru" in (j.get("location") or "").lower()
            or "bangalore" in (j.get("location") or "").lower()
        ]
    if quick_mode == "⚡ Core ECE":
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
runs = list_discovery_runs(limit=5)

last_sync = runs[0].get("run_at", "")[:16].replace("T", " ") + " UTC" if runs else "Ready to sync"
today_str = datetime.now().strftime("%Y-%m-%d")
submitted_today = sum(
    1 for a in apps if a.get("status") == "submitted" and str(a.get("submitted_at") or "").startswith(today_str)
)
submitted_total = sum(1 for a in apps if a.get("status") == "submitted")
# Use total submitted if today's timestamp is in UTC or earlier
goal_progress_count = max(submitted_today, 0)
goal_pct = min(100, int((goal_progress_count / max(1, daily_goal)) * 100))

# ================= HERO BANNER =================
st.markdown(
    f"""
    <div class="hero-banner">
      <div class="hero-left">
        <h1>🎯 Sruthi AI Job Agent — Live Command Center</h1>
        <p>24h India Discovery • 2027 B.Tech ECE Guardrail • 1-Page ATS Resume Tailoring • Safe Playwright Autofill</p>
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

# ================= TOP KPI STRIP =================
likely_count = sum(1 for j in active_jobs if j.get("eligibility_status") == "Likely eligible")
blr_count = sum(
    1
    for j in active_jobs
    if "bengaluru" in (j.get("location") or "").lower()
    or "bangalore" in (j.get("location") or "").lower()
)
awaiting_count = sum(1 for a in apps if a.get("status") == "awaiting_approval")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Active Unapplied", len(active_jobs))
k2.metric("Likely Eligible", likely_count)
k3.metric("Bengaluru Priority", blr_count)
k4.metric("Awaiting Approval", awaiting_count)
k5.metric("Total Submitted", submitted_total)

st.write("")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Live Dashboard", "🔍 Discover & Queue", "📋 Applications", "🏢 Company Directory", "👤 Profile"]
)

# ================= TAB 1: LIVE DASHBOARD =================
with tab1:
    # Quick-filter bar
    quick_mode = st.segmented_control(
        "Quick Focus",
        ["All", "🔥 Bengaluru Only", "⚡ Core ECE", "💻 IT / Software", "⭐ Score 70+"],
        default="All",
        label_visibility="collapsed",
    ) or "All"

    filtered_jobs = _apply_filters(active_jobs, quick_mode=quick_mode)

    # 1. Spotlight: Top 3 Priority Matches
    st.markdown(
        f'<div class="panel-header">🔥 Top Priority Matches to Apply Right Now ({len(filtered_jobs)} ready)</div>',
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
                        with st.spinner("Preparing package..."):
                            try:
                                pkg = prepare_application_package(job, profile)
                                st.success(f"Queued App #{pkg['application_id']}!")
                            except Exception as e:
                                st.error(str(e))
                with b2:
                    if job.get("url"):
                        st.link_button("🔗 Open", job["url"], width="stretch")
                with b3:
                    if st.button("🙈 Hide", key=f"dash_hide_{job['id']}", width="stretch"):
                        dismiss_job(job["id"], reason_status="dismissed")
                        st.rerun()
    else:
        st.info("No active jobs match this quick filter. Switch to 'All' or run a fresh 24h discovery.")

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

    if runs:
        with st.expander("🕒 Recent Discovery Runs Log", expanded=False):
            run_cols = [
                "run_at",
                "jobs_fetched",
                "jobs_matched",
                "new_jobs_inserted",
                "duplicates_skipped",
                "expired_marked",
                "error_count",
            ]
            st.dataframe([{k: r.get(k) for k in run_cols} for r in runs], width="stretch", hide_index=True)

# ================= TAB 2: DISCOVER & QUEUE =================
with tab2:
    filtered_feed = _apply_filters(active_jobs)
    st.subheader("Active Job Feed & Manual Entry")
    st.caption("Already-applied and hidden jobs are permanently excluded from this feed and future daily runs.")

    c_add, c_csv = st.columns(2)
    with c_add:
        with st.expander("➕ Add a job manually"):
            with st.form("add_job"):
                title = st.text_input("Job title")
                company = st.text_input("Company")
                location = st.text_input("Location", value="Bengaluru, India")
                url = st.text_input("Job URL")
                source = st.selectbox(
                    "Source",
                    ["Manual", "Company careers", "LinkedIn", "Indeed", "Naukri", "Greenhouse", "Lever", "Other"],
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
                        with st.spinner("Generating tailored resume, ATS score & screening answers..."):
                            try:
                                analysis = st.session_state.get(f"analysis_{job['id']}")
                                pkg = prepare_application_package(job, profile, analysis=analysis)
                                ats_val = (pkg.get("ats_report") or {}).get("ats_score", "N/A")
                                st.success(
                                    f"Queued Application #{pkg['application_id']} (ATS Score: {ats_val}/100). "
                                    "Open the Applications tab to review & approve."
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
                    if st.button("Generate tailored resume + ATS score", key=f"resume_{job['id']}"):
                        path, ats = create_tailored_resume_with_ats(profile, analysis, job)
                        st.success(f"Resume created: {path} | ATS Score: {ats['ats_score']}/100 ({ats['grade']})")
                        with open(path, "rb") as f:
                            st.download_button(
                                "Download tailored resume",
                                f,
                                file_name=Path(path).name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"download_{job['id']}",
                            )

# ================= TAB 3: APPLICATIONS =================
with tab3:
    st.subheader("Application Queue (Approval Required)")
    st.caption(
        "Workflow: Prepare Package → Review ATS Score & Answers → Approve → Launch Autofill Browser → Manual Submit → Mark Submitted."
    )

    apps_detailed = list_applications_detailed()
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "awaiting_approval", "approved", "submitted", "rejected"],
    )
    filtered_apps = (
        apps_detailed
        if status_filter == "All"
        else [a for a in apps_detailed if a.get("status") == status_filter]
    )

    if not filtered_apps:
        st.info("No applications in this status. Click 'Prepare' on any job in Live Dashboard or Discover & Queue.")
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
                else:
                    st.warning("Resume file not found on disk.")

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
                    st.success(f"Approved at {app_row.get('approved_at')}. Ready for manual review & submission.")
                    c_auto, c_sub = st.columns(2)
                    with c_auto:
                        if st.button("🌐 Launch Autofill Browser (Prefill & Pause)", key=f"autofill_{app_id}", type="primary", width="stretch"):
                            try:
                                res = launch_prefill_browser(
                                    job_url=app_row.get("url") or "",
                                    profile=profile,
                                    resume_path=str(resume_file),
                                )
                                st.info(
                                    f"Prefilled fields: {', '.join(res['filled_fields']) or 'None'}. "
                                    "Click 'Mark as Submitted' once you finish submitting in the browser."
                                )
                            except Exception as e:
                                st.error(str(e))
                    with c_sub:
                        if st.button("✔️ Mark as Submitted (After Manual Submit)", key=f"submit_{app_id}", width="stretch"):
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

# ================= TAB 4: COMPANY DIRECTORY =================
with tab4:
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

# ================= TAB 5: PROFILE =================
with tab5:
    st.subheader("Verified Candidate Profile")
    st.caption("Edit `data/profile.json` to maintain the verified master profile. No unverified facts are ever fabricated.")
    st.json(profile)