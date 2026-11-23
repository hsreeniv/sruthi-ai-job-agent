# Sruthi AI Job Agent

A local-first job discovery, Gemini analysis and resume-preparation app for a 2027 B.Tech ECE fresher. Final applications require explicit candidate approval.

## 1. Requirements
- Windows 10/11
- Python 3.11+
- Google AI Studio API key (separate from Gemini AI Pro subscription)

## 2. Setup (PowerShell)
```powershell
cd sruthi_ai_job_agent
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```
Edit `.env` and add your Gemini API key. Never share or commit `.env`.

## 3. Run
```powershell
streamlit run app.py
```

## 4. First configuration
Edit `data/profile.json` and replace all placeholders with Sruthi's verified details. Do not leave example skills or project descriptions as factual claims.

## 5. Current capabilities
- Manual job entry
- CSV job import
- SQLite deduplication
- Gemini job-fit analysis (JSON)
- DOCX resume draft from verified master profile
- Dashboard and application tracking foundation

## 6. Phase 2: public job discovery

1. Add verified Greenhouse, Lever and Ashby company board slugs to `config/boards.json`.
2. Set each entry's `enabled` to `true`.
3. Run `python run_discovery.py`, or click **Run discovery now** in the Discover tab.
4. For daily 07:00 IST refresh, run `python schedule_discovery.py` and keep it running, or register `run_discovery.py` in Windows Task Scheduler.

The connectors use public GET job-board endpoints. They fetch per-company postings, normalize descriptions and store likely IT/Core ECE matches. The 100-job target is a cap; actual results depend on enabled boards and live openings. Heuristic matching is preliminary and must be followed by Gemini eligibility analysis.

## 7. Next implementation milestones
1. Public job-source connectors (company career feeds, Greenhouse/Lever public job boards, permitted aggregators).
2. Daily scheduler and notification summary.
3. Gemini resume rewriting with factuality checks and PDF export.
4. Playwright form preparation adapters, starting with a controlled demo form.
5. Approval queue and explicit submit action.

## Safety and platform constraints
Use official/public job feeds and permitted integrations. Do not bypass CAPTCHA, OTP, access controls or site terms. Browser automation must stop for human verification where needed. The agent must not guess answers to legal, eligibility, work-authorization, demographic or other sensitive screening questions.
