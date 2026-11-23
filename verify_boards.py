"""Verify public ATS board identifiers live before enabling them in config/boards.json.

Only boards that return HTTP 200 with valid JSON postings are marked active and enabled.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

CONFIG_PATH = Path("config/boards.json")
SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "SruthiAIJobAgent/2.2 (public-ats-verifier)",
        "Accept": "application/json",
    }
)
TIMEOUT = 15

INDIA_KEYWORDS = ("india", "bengaluru", "bangalore", "hyderabad", "pune", "chennai", "noida", "mumbai", "gurugram", "gurgaon")

# Candidate public slugs to probe live (NOT assumed valid until HTTP 200 succeeds)
CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "Bosch": [("smartrecruiters", "BoschGroup")],
    "Western Digital": [("smartrecruiters", "WesternDigital")],
    "Freshworks": [("smartrecruiters", "Freshworks")],
    "Razorpay": [("greenhouse", "razorpaysoftwareprivatelimited"), ("greenhouse", "razorpay")],
    "PhonePe": [("greenhouse", "phonepe")],
    "BrowserStack": [("greenhouse", "browserstack"), ("lever", "browserstack")],
    "CRED": [("lever", "cred"), ("greenhouse", "cred")],
    "Groww": [("lever", "groww"), ("greenhouse", "groww")],
    "Cloudflare": [("greenhouse", "cloudflare")],
    "Ather Energy": [("lever", "atherenergy"), ("greenhouse", "atherenergy")],
    "Zomato": [("lever", "zomato"), ("greenhouse", "zomato")],
    "Swiggy": [("lever", "swiggy"), ("greenhouse", "swiggy")],
}


def _count_india(items: list[str]) -> int:
    return sum(1 for loc in items if any(k in (loc or "").lower() for k in INDIA_KEYWORDS))


def probe_board(provider: str, slug: str) -> tuple[bool, int, int, str]:
    """Return (ok, total_jobs, india_jobs, detail)."""
    try:
        if provider == "greenhouse":
            url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
            r = SESSION.get(url, timeout=TIMEOUT)
            if r.status_code != 200:
                return False, 0, 0, f"HTTP {r.status_code}"
            jobs = r.json().get("jobs", [])
            locs = [(j.get("location") or {}).get("name", "") for j in jobs]
            return True, len(jobs), _count_india(locs), "OK"

        if provider == "lever":
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            r = SESSION.get(url, timeout=TIMEOUT)
            if r.status_code != 200:
                return False, 0, 0, f"HTTP {r.status_code}"
            jobs = r.json()
            if not isinstance(jobs, list):
                return False, 0, 0, "Unexpected JSON"
            locs = [(j.get("categories") or {}).get("location", "") for j in jobs]
            return True, len(jobs), _count_india(locs), "OK"

        if provider == "smartrecruiters":
            url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100"
            r = SESSION.get(url, timeout=TIMEOUT)
            if r.status_code != 200:
                return False, 0, 0, f"HTTP {r.status_code}"
            data = r.json()
            jobs = data.get("content", [])
            total = int(data.get("totalFound", len(jobs)))
            locs = [
                f"{(j.get('location') or {}).get('city', '')} {(j.get('location') or {}).get('country', '')}"
                for j in jobs
            ]
            return True, total, _count_india(locs), "OK"

        if provider == "ashby":
            url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
            r = SESSION.get(url, timeout=TIMEOUT)
            if r.status_code != 200:
                return False, 0, 0, f"HTTP {r.status_code}"
            jobs = r.json().get("jobs", [])
            locs = [j.get("location", "") for j in jobs]
            return True, len(jobs), _count_india(locs), "OK"

        return False, 0, 0, f"Unsupported provider: {provider}"
    except Exception as exc:
        return False, 0, 0, f"{type(exc).__name__}: {exc}"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    companies: list[dict[str, Any]] = config.get("companies", [])
    by_name = {c["company_name"]: c for c in companies}

    verified_count = 0
    print("Probing candidate public ATS endpoints...\n")

    for company_name, attempts in CANDIDATES.items():
        if company_name not in by_name:
            continue
        matched = False
        for provider, slug in attempts:
            ok, total, india_cnt, detail = probe_board(provider, slug)
            time.sleep(0.5)
            status_tag = "VERIFIED" if ok and total > 0 else "SKIP"
            print(
                f"[{status_tag:8}] {company_name:18} | {provider:15} | {slug:32} | total={total:4} | india_sample={india_cnt:3} | {detail}"
            )
            if ok and total > 0:
                entry = by_name[company_name]
                entry["ats_provider"] = provider
                entry["board_identifier"] = slug
                entry["connector_status"] = "active"
                entry["enabled"] = True
                verified_count += 1
                matched = True
                break
        if not matched:
            entry = by_name[company_name]
            if not entry.get("enabled"):
                entry["connector_status"] = "portal_only"

    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    enabled_total = sum(1 for c in companies if c.get("enabled"))
    print(f"\nUpdated {CONFIG_PATH}. Verified & enabled boards: {enabled_total} (newly verified: {verified_count}).")


if __name__ == "__main__":
    main()