from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

LOG = logging.getLogger(__name__)

# Complete 2027 Core ECE + IT/Software query pack (Past 24h, India-wide)
CORE_ECE_QUERIES = [
    '"Graduate Engineer Trainee" ECE',
    "Embedded Systems Intern 2027",
    "VLSI Intern 2027",
    "Hardware Engineer Intern",
    "Firmware Engineer Intern",
    "Network Engineer Fresher",
    "Telecom Engineer Trainee",
]

IT_SOFTWARE_QUERIES = [
    "University Graduate 2027",
    "Software Engineer Intern 2027",
    "SDE Intern 2027",
    "Associate Software Engineer 2027",
    "Campus Hiring 2027",
    "AI ML Intern 2027",
]

DEFAULT_QUERIES = CORE_ECE_QUERIES + IT_SOFTWARE_QUERIES


def _fetch_linkedin_guest_24h(
    query: str,
    location: str = "India",
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Public LinkedIn guest jobs endpoint filtered strictly to past 24 hours (f_TPR=r86400)."""
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {
        "keywords": query,
        "location": location,
        "f_TPR": "r86400",  # Past 24 hours
        "start": 0,
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    jobs: list[dict[str, Any]] = []
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("li")[:limit]:
            title_el = card.select_one("h3.base-search-card__title")
            comp_el = card.select_one("h4.base-search-card__subtitle")
            loc_el = card.select_one("span.job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")
            if not title_el or not comp_el:
                continue
            job_url = (link_el.get("href") or "").split("?")[0] if link_el else ""
            title_txt = title_el.get_text(strip=True)
            comp_txt = comp_el.get_text(strip=True)
            loc_txt = loc_el.get_text(strip=True) if loc_el else location
            jobs.append(
                {
                    "title": title_txt,
                    "company": comp_txt,
                    "location": loc_txt,
                    "url": job_url,
                    "source": "LinkedIn (24h)",
                    "jd": f"{title_txt} at {comp_txt} | Query: {query}. Open URL to review full JD.",
                }
            )
    except Exception as exc:
        LOG.warning("LinkedIn guest fallback failed for '%s': %s", query, exc)
    return jobs


def _dedupe_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for j in jobs:
        url_key = (j.get("url") or "").strip().lower()
        pair_key = (
            (j.get("company") or "").strip().lower(),
            (j.get("title") or "").strip().lower(),
        )
        if url_key and url_key in seen_urls:
            continue
        if pair_key in seen_pairs:
            continue
        if url_key:
            seen_urls.add(url_key)
        seen_pairs.add(pair_key)
        unique.append(j)
    return unique


def fetch_multi_source_24h(
    queries: list[str] | None = None,
    location: str = "India",
    hours_old: int = 24,
    results_per_site: int = 10,
    sites: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch past-24h jobs across LinkedIn, Indeed, and Naukri for all target queries.

    Returns (deduplicated_jobs, error_messages).
    """
    search_terms = queries or DEFAULT_QUERIES
    target_sites = sites or ["linkedin", "indeed", "naukri"]
    collected: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        from jobspy import scrape_jobs  # type: ignore
    except ImportError:
        errors.append("python-jobspy not installed; using LinkedIn 24h guest fallback only.")
        for q in search_terms:
            collected.extend(_fetch_linkedin_guest_24h(q, location=location, limit=results_per_site))
            time.sleep(2.5)
        return _dedupe_jobs(collected), errors

    for q in search_terms:
        clean_q = q.replace('"', "")
        try:
            df = scrape_jobs(
                site_name=target_sites,
                search_term=q,
                location=location,
                results_wanted=results_per_site,
                hours_old=hours_old,
                country_indeed="India",
                linkedin_fetch_description=False,
            )
            if df is None or df.empty:
                collected.extend(_fetch_linkedin_guest_24h(q, location=location, limit=results_per_site))
            else:
                for _, row in df.iterrows():
                    title = str(row.get("title") or "").strip()
                    company = str(row.get("company") or "").strip()
                    loc = str(row.get("location") or location).strip()
                    url = str(row.get("job_url") or row.get("job_url_direct") or "").strip()
                    site = str(row.get("site") or "JobBoard").strip().title()
                    desc = str(row.get("description") or "").strip()
                    if not desc or desc.lower() == "nan":
                        desc = f"{title} at {company} | Query: {clean_q}."
                    desc = re.sub(r"\s+", " ", desc)[:4000]

                    if title and company:
                        collected.append(
                            {
                                "title": title,
                                "company": company,
                                "location": loc if loc.lower() != "nan" else location,
                                "url": url if url.lower() != "nan" else "",
                                "source": f"{site} (24h)",
                                "jd": desc,
                            }
                        )
        except Exception as exc:
            errors.append(f"Multi-source fetch failed for '{q}': {exc}")
            collected.extend(_fetch_linkedin_guest_24h(q, location=location, limit=10))
        finally:
            time.sleep(2.5)  # Prevent LinkedIn 429 rate-limit spikes

    return _dedupe_jobs(collected), errors