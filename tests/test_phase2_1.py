from __future__ import annotations

import json
from pathlib import Path

import src.db as db
from src.discovery import discover_and_store
from src.eligibility import ELIGIBLE, INELIGIBLE, REVIEW, evaluate_job, sort_jobs_bengaluru_first


SAMPLE_PROFILE = {
    "name": "M. Sruthi",
    "degree": "B.Tech – Electronics and Communication Engineering",
    "passout_year": 2027,
    "backlogs": "No active backlogs",
    "experience_level": "Fresher",
    "locations": ["Bengaluru (priority)", "Anywhere in India"],
    "tracks": ["IT", "Core Engineering"],
    "skills": ["Python", "NumPy", "scikit-learn", "Data Analysis"],
}


def test_save_job_distinguishes_inserted_and_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    r1 = db.save_job(
        title="Software Intern 2027",
        company="Postman",
        location="Bengaluru, India",
        url="https://boards.greenhouse.io/postman/jobs/101",
        source="Greenhouse",
        jd="Python internship for 2027 batch.",
        external_id="101",
    )
    r2 = db.save_job(
        title="Software Intern 2027",
        company="Postman",
        location="Bengaluru, India",
        url="https://boards.greenhouse.io/postman/jobs/101",
        source="Greenhouse",
        jd="Python internship for 2027 batch.",
        external_id="101",
    )

    assert r1["status"] == "inserted"
    assert r2["status"] == "duplicate"
    assert len(db.list_jobs()) == 1


def test_mark_missing_jobs_expired(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    r1 = db.save_job(
        title="Intern A",
        company="Cloudflare",
        location="Bengaluru",
        source="Greenhouse",
        jd="Python",
        external_id="A1",
    )
    r2 = db.save_job(
        title="Intern B",
        company="Cloudflare",
        location="Bengaluru",
        source="Greenhouse",
        jd="Python",
        external_id="B2",
    )

    expired = db.mark_missing_jobs_expired("Cloudflare", "Greenhouse", {r1["dedupe_key"]})
    assert expired == 1
    active = db.list_jobs(include_expired=False)
    assert len(active) == 1
    assert active[0]["id"] == r1["job_id"]
    assert len(db.list_jobs(include_expired=True)) == 2


def test_eligibility_three_tiers_and_2027_guardrail():
    # 1. Explicit 2027 internship in Bengaluru -> Likely eligible
    j_eligible = evaluate_job(
        {
            "title": "Data Analytics Intern 2027",
            "location": "Bengaluru, India",
            "jd": "Open to 2027 batch B.Tech ECE students with Python, NumPy, and no active backlogs.",
        },
        SAMPLE_PROFILE,
    )
    assert j_eligible["eligibility_status"] == ELIGIBLE
    assert j_eligible["bengaluru_priority"] is True

    # 2. Fresher/Trainee title WITHOUT explicit 2027 batch -> Review required (never auto-eligible)
    j_review = evaluate_job(
        {
            "title": "Graduate Engineer Trainee",
            "location": "Bengaluru, India",
            "jd": "Looking for B.Tech ECE freshers with Python skills.",
        },
        SAMPLE_PROFILE,
    )
    assert j_review["eligibility_status"] == REVIEW

    # 3. Explicit 2025 batch restriction -> Ineligible
    j_wrong_batch = evaluate_job(
        {
            "title": "Graduate Trainee",
            "location": "Bengaluru, India",
            "jd": "Strictly for 2025 batch B.Tech graduates.",
        },
        SAMPLE_PROFILE,
    )
    assert j_wrong_batch["eligibility_status"] == INELIGIBLE

    # 4. Senior role / 5+ years -> Ineligible
    j_senior = evaluate_job(
        {
            "title": "Senior Embedded Engineer",
            "location": "Bengaluru, India",
            "jd": "Minimum 5+ years experience in Embedded C and RTOS.",
        },
        SAMPLE_PROFILE,
    )
    assert j_senior["eligibility_status"] == INELIGIBLE


def test_bengaluru_first_ranking():
    jobs = [
        {"title": "Intern Hyd", "eligibility_status": ELIGIBLE, "bengaluru_priority": False, "match_score": 85},
        {"title": "Intern Blr", "eligibility_status": ELIGIBLE, "bengaluru_priority": True, "match_score": 80},
        {"title": "Review Blr", "eligibility_status": REVIEW, "bengaluru_priority": True, "match_score": 90},
    ]
    ranked = sort_jobs_bengaluru_first(jobs)
    assert ranked[0]["title"] == "Intern Blr"
    assert ranked[1]["title"] == "Intern Hyd"
    assert ranked[2]["title"] == "Review Blr"


def test_discover_and_store_counts_duplicates_accurately(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    cfg_path = tmp_path / "boards.json"
    cfg_path.write_text(
        json.dumps(
            {
                "companies": [
                    {
                        "company_name": "MockCo",
                        "career_url": "https://mockco.example/careers",
                        "ats_provider": "greenhouse",
                        "board_identifier": "mockco",
                        "category": "Product",
                        "location": "Bengaluru",
                        "connector_status": "active",
                        "enabled": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    fake_jobs = [
        {
            "company": "MockCo",
            "source": "Greenhouse",
            "external_id": "9001",
            "title": "Python Data Intern 2027",
            "location": "Bengaluru, India",
            "url": "https://mockco.example/jobs/9001",
            "jd": "2027 batch B.Tech ECE internship requiring Python and Data Analysis.",
            "posted_at": "2026-11-20",
            "employment_type": "Internship",
        }
    ]

    def fake_fetch(_config):
        return (
            fake_jobs,
            [],
            [
                {
                    "entry": _config["companies"][0],
                    "company": "MockCo",
                    "provider": "greenhouse",
                    "status": "active",
                    "fetched_count": 1,
                    "error": None,
                    "fetched_at": "2026-11-23T03:00:00+00:00",
                    "jobs": fake_jobs,
                }
            ],
        )

    monkeypatch.setattr("src.discovery.fetch_configured_boards", fake_fetch)

    first = discover_and_store(SAMPLE_PROFILE, target=100, config_path=cfg_path)
    second = discover_and_store(SAMPLE_PROFILE, target=100, config_path=cfg_path)

    assert first["fetched"] == 1
    assert first["matched"] == 1
    assert first["inserted"] == 1
    assert first["duplicates_skipped"] == 0

    assert second["fetched"] == 1
    assert second["matched"] == 1
    assert second["inserted"] == 0
    assert second["duplicates_skipped"] == 1