from __future__ import annotations

from src.autofill import _parse_contact_line
from src.eligibility import evaluate_job
from src.profile import load_profile
from src.sources.job_boards import _dedupe_jobs


def test_evaluate_job_accepts_bengaluru_2027_intern():
    profile = load_profile()
    job = {
        "title": "Embedded Systems Intern 2027",
        "company": "Qualcomm",
        "location": "Bengaluru, Karnataka, India",
        "source": "LinkedIn (24h)",
        "jd": "Hiring 2027 B.Tech ECE students for Embedded C, Python, UART, SPI, I2C internship in Bengaluru.",
    }
    result = evaluate_job(job, profile)
    assert result.get("eligible") or result.get("discovery_candidate")
    assert result.get("match_score", 0) >= 50


def test_evaluate_job_rejects_senior_or_non_india():
    profile = load_profile()
    senior_job = {
        "title": "Senior Staff Firmware Architect (8+ Years)",
        "company": "ExampleCorp",
        "location": "San Jose, California, USA",
        "source": "LinkedIn (24h)",
        "jd": "Requires 8+ years of experience in kernel architecture. Must be authorized to work in the US.",
    }
    result = evaluate_job(senior_job, profile)
    assert not result.get("eligible")
    assert result.get("eligibility_status") != "Likely eligible"


def test_dedupe_jobs_removes_url_and_title_duplicates():
    jobs = [
        {"company": "Bosch", "title": "ECE Intern", "url": "https://example.com/1"},
        {"company": "Bosch", "title": "ECE Intern", "url": "https://example.com/1"},
        {"company": "bosch", "title": "ece intern", "url": "https://example.com/2"},
        {"company": "Qualcomm", "title": "VLSI Intern", "url": "https://example.com/3"},
    ]
    unique = _dedupe_jobs(jobs)
    assert len(unique) == 2


def test_parse_contact_line_extracts_verified_fields():
    line = "Kuppam, Andhra Pradesh | +91 9876543210 | sruthi@example.com | https://www.linkedin.com/in/sruthi-m"
    parsed = _parse_contact_line(line)
    assert parsed["email"] == "sruthi@example.com"
    assert "9876543210" in parsed["phone"]
    assert parsed["linkedin"] == "https://www.linkedin.com/in/sruthi-m"
    assert "Kuppam" in parsed["city"]