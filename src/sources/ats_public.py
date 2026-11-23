"""Public job-board connectors (GET / public JSON feeds only).

No login, CAPTCHA bypass, or automated application submission.
"""
from __future__ import annotations

import html
import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

LOG = logging.getLogger(__name__)
SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "SruthiAIJobAgent/2.1 (public-careers-feed-reader)",
        "Accept": "application/json, text/plain, */*",
    }
)
TIMEOUT = 25
PAUSE_SECONDS = 0.8


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    response = SESSION.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    time.sleep(PAUSE_SECONDS)
    return response.json()


def _post_json(url: str, payload: dict[str, Any]) -> Any:
    response = SESSION.post(
        url,
        json=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    time.sleep(PAUSE_SECONDS)
    return response.json()


def _plain_text(value: str | None) -> str:
    if not value:
        return ""
    decoded = html.unescape(value)
    return BeautifulSoup(decoded, "html.parser").get_text(" ", strip=True)


def _normalized(
    company: str,
    source: str,
    external_id: str,
    title: str,
    location: str,
    url: str,
    description: str,
    posted_at: str = "",
    employment_type: str = "",
) -> dict[str, Any]:
    return {
        "company": company,
        "source": source,
        "external_id": str(external_id or ""),
        "title": (title or "").strip(),
        "location": (location or "Not specified").strip(),
        "url": (url or "").strip(),
        "jd": _plain_text(description),
        "posted_at": str(posted_at or "").strip(),
        "employment_type": (employment_type or "").strip(),
    }


def greenhouse(company: str, board: str) -> list[dict[str, Any]]:
    """Greenhouse public Job Board API: /v1/boards/{board}/jobs?content=true."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    data = _get_json(url)
    jobs: list[dict[str, Any]] = []
    for item in data.get("jobs", []):
        jobs.append(
            _normalized(
                company=company,
                source="Greenhouse",
                external_id=str(item.get("id", "")),
                title=item.get("title", ""),
                location=(item.get("location") or {}).get("name", ""),
                url=item.get("absolute_url", ""),
                description=item.get("content", ""),
                posted_at=item.get("first_published") or item.get("updated_at", ""),
            )
        )
    return jobs


def lever(company: str, site: str, region: str = "global") -> list[dict[str, Any]]:
    """Lever public Postings API; region can be global or eu."""
    host = "api.eu.lever.co" if region.lower() == "eu" else "api.lever.co"
    data = _get_json(f"https://{host}/v0/postings/{site}?mode=json")
    if not isinstance(data, list):
        LOG.warning("Lever returned unexpected payload for site %s", site)
        return []
    jobs: list[dict[str, Any]] = []
    for item in data:
        cats = item.get("categories") or {}
        loc = (
            ", ".join(cats["allLocations"])
            if cats.get("allLocations")
            else cats.get("location", "")
        )
        jobs.append(
            _normalized(
                company=company,
                source="Lever",
                external_id=str(item.get("id", "")),
                title=item.get("text", ""),
                location=loc,
                url=item.get("hostedUrl") or item.get("applyUrl", ""),
                description=item.get("descriptionPlain") or item.get("description", ""),
                posted_at=str(item.get("createdAt", "")),
                employment_type=cats.get("commitment", ""),
            )
        )
    return jobs


def ashby(company: str, board: str) -> list[dict[str, Any]]:
    """Ashby public posting API."""
    data = _get_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
    )
    jobs: list[dict[str, Any]] = []
    for item in data.get("jobs", []):
        locations = [item.get("location", "")]
        locations.extend(item.get("secondaryLocations") or [])
        jobs.append(
            _normalized(
                company=company,
                source="Ashby",
                external_id=str(item.get("id", "")),
                title=item.get("title", ""),
                location=", ".join(x for x in locations if x),
                url=item.get("jobUrl") or item.get("applyUrl", ""),
                description=item.get("descriptionPlain") or item.get("descriptionHtml", ""),
                posted_at=item.get("publishedAt", ""),
                employment_type=item.get("employmentType", ""),
            )
        )
    return jobs


def smartrecruiters(
    company: str,
    company_identifier: str,
    limit: int = 100,
    fetch_details: bool = False,
) -> list[dict[str, Any]]:
    """SmartRecruiters public postings API."""
    base_url = f"https://api.smartrecruiters.com/v1/companies/{company_identifier}/postings"
    data = _get_json(base_url, params={"limit": min(limit, 100), "offset": 0})
    postings = data.get("content", [])
    jobs: list[dict[str, Any]] = []

    for item in postings:
        posting_id = str(item.get("id", ""))
        loc_obj = item.get("location") or {}
        loc_parts = [loc_obj.get("city", ""), loc_obj.get("region", ""), loc_obj.get("country", "")]
        location = ", ".join(p for p in loc_parts if p)
        if loc_obj.get("remote"):
            location = f"{location} (Remote)".strip()

        dept = (item.get("department") or {}).get("label", "")
        emp_type = (item.get("typeOfEmployment") or {}).get("label", "")
        exp_level = (item.get("experienceLevel") or {}).get("label", "")
        posting_url = item.get("ref", "")
        public_url = f"https://jobs.smartrecruiters.com/{company_identifier}/{posting_id}"

        description = f"Department: {dept}. Employment Type: {emp_type}. Experience Level: {exp_level}."
        if fetch_details and posting_url:
            try:
                detail = _get_json(posting_url)
                sections = (detail.get("jobAd") or {}).get("sections") or {}
                parts = [
                    (sections.get("jobDescription") or {}).get("text", ""),
                    (sections.get("qualifications") or {}).get("text", ""),
                    (sections.get("additionalInformation") or {}).get("text", ""),
                ]
                combined = "\n".join(p for p in parts if p)
                if combined.strip():
                    description = combined
            except Exception as exc:
                LOG.debug("SmartRecruiters detail fetch skipped for %s: %s", posting_id, exc)

        jobs.append(
            _normalized(
                company=company,
                source="SmartRecruiters",
                external_id=posting_id,
                title=item.get("name", ""),
                location=location,
                url=public_url,
                description=description,
                posted_at=item.get("releasedDate", ""),
                employment_type=emp_type,
            )
        )
    return jobs


def workday(
    company: str,
    tenant: str,
    wd_instance: str,
    site: str,
    search_text: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Workday public career CXS JSON endpoint (where publicly permitted)."""
    base_host = f"https://{tenant}.{wd_instance}.myworkdayjobs.com"
    api_url = f"{base_host}/wday/cxs/{tenant}/{site}/jobs"
    payload = {
        "appliedFacets": {},
        "limit": min(limit, 20),
        "offset": 0,
        "searchText": search_text,
    }
    data = _post_json(api_url, payload)
    postings = data.get("jobPostings", [])
    jobs: list[dict[str, Any]] = []

    for item in postings:
        ext_path = item.get("externalPath", "")
        bullet_fields = item.get("bulletFields") or []
        ext_id = bullet_fields[0] if bullet_fields else ext_path
        full_url = f"{base_host}/en-US/{site}{ext_path}" if ext_path else f"{base_host}/en-US/{site}"
        jobs.append(
            _normalized(
                company=company,
                source="Workday",
                external_id=str(ext_id),
                title=item.get("title", ""),
                location=item.get("locationsText", ""),
                url=full_url,
                description=f"Workday public posting. Req ID: {ext_id}. Posted: {item.get('postedOn', '')}.",
                posted_at=item.get("postedOn", ""),
                employment_type=item.get("timeType", ""),
            )
        )
    return jobs


def _iter_directory_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Support both new unified `companies` list and legacy provider-keyed boards.json."""
    if isinstance(config.get("companies"), list):
        return config["companies"]

    entries: list[dict[str, Any]] = []
    for provider, items in config.items():
        if not isinstance(items, list):
            continue
        for item in items:
            entry = dict(item)
            entry.setdefault("ats_provider", provider)
            entry.setdefault("company_name", item.get("company", "Unknown"))
            entry.setdefault(
                "board_identifier",
                item.get("board") or item.get("site") or "",
            )
            entries.append(entry)
    return entries


def fetch_configured_boards(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """Fetch all enabled, verified boards.

    Returns:
        (all_jobs, errors, board_results)
    """
    all_jobs: list[dict[str, Any]] = []
    errors: list[str] = []
    board_results: list[dict[str, Any]] = []

    for entry in _iter_directory_entries(config):
        company = entry.get("company_name") or entry.get("company") or "Unknown"
        provider = (entry.get("ats_provider") or "").strip().lower()
        board_id = (entry.get("board_identifier") or entry.get("board") or entry.get("site") or "").strip()
        enabled = bool(entry.get("enabled", False))

        if not enabled:
            continue

        if not board_id and provider != "workday":
            msg = f"{provider} / {company}: Missing verified board identifier."
            errors.append(msg)
            board_results.append(
                {
                    "entry": entry,
                    "company": company,
                    "provider": provider,
                    "status": "error",
                    "fetched_count": 0,
                    "error": msg,
                    "fetched_at": None,
                }
            )
            continue

        try:
            if provider == "greenhouse":
                jobs = greenhouse(company, board_id)
            elif provider == "lever":
                jobs = lever(company, board_id, entry.get("region", "global"))
            elif provider == "ashby":
                jobs = ashby(company, board_id)
            elif provider == "smartrecruiters":
                jobs = smartrecruiters(
                    company,
                    board_id,
                    fetch_details=bool(entry.get("fetch_details", False)),
                )
            elif provider == "workday":
                jobs = workday(
                    company=company,
                    tenant=entry["workday_tenant"],
                    wd_instance=entry["workday_instance"],
                    site=entry["workday_site"],
                    search_text=entry.get("search_text", ""),
                )
            else:
                msg = f"{provider} / {company}: Provider not automated in Phase 2.1 (official portal only)."
                board_results.append(
                    {
                        "entry": entry,
                        "company": company,
                        "provider": provider,
                        "status": "portal_only",
                        "fetched_count": 0,
                        "error": None,
                        "fetched_at": None,
                    }
                )
                continue

            all_jobs.extend(jobs)
            board_results.append(
                {
                    "entry": entry,
                    "company": company,
                    "provider": provider,
                    "status": "active",
                    "fetched_count": len(jobs),
                    "error": None,
                    "fetched_at": _utc_now(),
                    "jobs": jobs,
                }
            )
            LOG.info("%s / %s: fetched %d postings", provider, company, len(jobs))
        except Exception as exc:
            msg = f"{provider} / {company}: {type(exc).__name__}: {exc}"
            errors.append(msg)
            LOG.warning(msg)
            board_results.append(
                {
                    "entry": entry,
                    "company": company,
                    "provider": provider,
                    "status": "error",
                    "fetched_count": 0,
                    "error": msg,
                    "fetched_at": None,
                }
            )

    return all_jobs, errors, board_results