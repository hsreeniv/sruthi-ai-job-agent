from __future__ import annotations

import logging
import random
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

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


def _fetch_linkedin_guest_24h(
    query: str,
    location: str = "India",
    limit: int = 15,
) -> tuple[list[dict[str, Any]], bool]:
    """Public LinkedIn guest jobs endpoint filtered strictly to past 24 hours (f_TPR=r86400).

    Returns (jobs, rate_limited).
    """
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {
        "keywords": query,
        "location": location,
        "f_TPR": "r86400",  # Past 24 hours
        "start": 0,
    }
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    jobs: list[dict[str, Any]] = []
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 429:
            LOG.warning("LinkedIn guest rate-limited (429) on '%s'. Circuit breaker tripped.", query)
            return [], True
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
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            LOG.warning("LinkedIn guest rate-limited (429) on '%s'. Circuit breaker tripped.", query)
            return [], True
        LOG.warning("LinkedIn guest fallback failed for '%s': %s", query, exc)
    except Exception as exc:
        LOG.warning("LinkedIn guest fallback failed for '%s': %s", query, exc)
    return jobs, False


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
    linkedin_rate_limited = False

    try:
        from jobspy import scrape_jobs  # type: ignore
    except ImportError:
        errors.append("python-jobspy not installed; using LinkedIn 24h guest fallback only.")
        for idx, q in enumerate(search_terms):
            if linkedin_rate_limited:
                break
            if idx > 0:
                time.sleep(random.uniform(2.5, 4.5))
            guest_jobs, rate_limited = _fetch_linkedin_guest_24h(q, location=location, limit=results_per_site)
            collected.extend(guest_jobs)
            if rate_limited:
                linkedin_rate_limited = True
                errors.append("LinkedIn rate-limited (429); skipped remaining LinkedIn guest queries for this run.")
                break
        return _dedupe_jobs(collected), errors

    for idx, q in enumerate(search_terms):
        clean_q = q.replace('"', "")
        active_sites = [s for s in target_sites if not (linkedin_rate_limited and s.lower() == "linkedin")]
        if not active_sites:
            break

        try:
            df = scrape_jobs(
                site_name=active_sites,
                search_term=q,
                location=location,
                results_wanted=results_per_site,
                hours_old=hours_old,
                country_indeed="India",
                linkedin_fetch_description=False,
            )
            if df is None or df.empty:
                if not linkedin_rate_limited:
                    guest_jobs, rate_limited = _fetch_linkedin_guest_24h(
                        q, location=location, limit=results_per_site
                    )
                    collected.extend(guest_jobs)
                    if rate_limited:
                        linkedin_rate_limited = True
                        errors.append("LinkedIn rate-limited (429); skipped remaining LinkedIn guest queries.")
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
            if not linkedin_rate_limited:
                guest_jobs, rate_limited = _fetch_linkedin_guest_24h(q, location=location, limit=10)
                collected.extend(guest_jobs)
                if rate_limited:
                    linkedin_rate_limited = True
                    errors.append("LinkedIn rate-limited (429); skipped remaining LinkedIn guest queries.")
        finally:
            if idx < len(search_terms) - 1:
                time.sleep(random.uniform(2.5, 4.0))

    return _dedupe_jobs(collected), errors