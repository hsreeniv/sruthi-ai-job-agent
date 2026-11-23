from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.db import (
    build_dedupe_key,
    mark_missing_jobs_expired,
    record_discovery_run,
    save_job,
    upsert_company_status,
)
from src.eligibility import evaluate_job, sort_jobs_bengaluru_first
from src.sources.ats_public import _iter_directory_entries, fetch_configured_boards
from src.sources.job_boards import fetch_multi_source_24h

LOG = logging.getLogger(__name__)
CONFIG_PATH = Path("config/boards.json")


def load_board_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing board configuration file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def classify_and_score(job: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible wrapper around the Phase 2.1 Eligibility Engine."""
    return evaluate_job(job, profile)


def sync_company_directory(config: dict[str, Any]) -> int:
    """Sync all configured companies into the SQLite company_directory table."""
    entries = _iter_directory_entries(config)
    for entry in entries:
        upsert_company_status(
            company_name=entry.get("company_name") or entry.get("company") or "Unknown",
            career_url=entry.get("career_url", ""),
            ats_provider=entry.get("ats_provider", ""),
            board_identifier=entry.get("board_identifier")
            or entry.get("board")
            or entry.get("site")
            or "",
            category=entry.get("category", ""),
            location=entry.get("location", ""),
            connector_status=entry.get(
                "connector_status",
                "active" if entry.get("enabled") else "pending_verification",
            ),
            enabled=bool(entry.get("enabled", False)),
        )
    return len(entries)


def build_daily_summary(
    fetched: int,
    matched: int,
    inserted: int,
    duplicates_skipped: int,
    expired_marked: int,
    errors: list[str],
    top_jobs: list[dict[str, Any]],
) -> str:
    blr_count = sum(
        1
        for j in top_jobs
        if j.get("bengaluru_priority")
        or "bengaluru" in (j.get("location") or "").lower()
        or "bangalore" in (j.get("location") or "").lower()
    )
    likely_count = sum(1 for j in top_jobs if j.get("eligibility_status") == "Likely eligible")
    review_count = sum(1 for j in top_jobs if j.get("eligibility_status") == "Review required")
    lines = [
        f"Fetched: {fetched} | Matched: {matched} | New inserted: {inserted} | Duplicates skipped: {duplicates_skipped} | Expired: {expired_marked} | Errors: {len(errors)}",
        f"Top batch breakdown -> Bengaluru: {blr_count} | Likely eligible: {likely_count} | Review required: {review_count}",
    ]
    return "\n".join(lines)


def discover_and_store(
    profile: dict[str, Any],
    target: int = 100,
    config_path: Path = CONFIG_PATH,
    include_job_boards: bool = True,
) -> dict[str, Any]:
    config = load_board_config(config_path)
    sync_company_directory(config)

    raw_jobs, errors, board_results = fetch_configured_boards(config)

    expired_marked = 0
    for br in board_results:
        entry = br["entry"]
        company = br["company"]
        provider = br["provider"]
        upsert_company_status(
            company_name=company,
            career_url=entry.get("career_url", ""),
            ats_provider=provider,
            board_identifier=entry.get("board_identifier")
            or entry.get("board")
            or entry.get("site")
            or "",
            category=entry.get("category", ""),
            location=entry.get("location", ""),
            connector_status=br["status"],
            enabled=bool(entry.get("enabled", False)),
            last_successful_fetch=br.get("fetched_at"),
            last_error=br.get("error"),
        )

        # Only mark expired if the board fetch succeeded cleanly
        if br["status"] == "active" and isinstance(br.get("jobs"), list):
            source_label = br["jobs"][0]["source"] if br["jobs"] else provider.capitalize()
            active_keys = {
                build_dedupe_key(
                    company=j["company"],
                    title=j["title"],
                    url=j.get("url", ""),
                    jd=j.get("jd", ""),
                    external_id=j.get("external_id", ""),
                    source=j.get("source", source_label),
                )
                for j in br["jobs"]
            }
            expired_marked += mark_missing_jobs_expired(company, source_label, active_keys)

    # Merge past-24h jobs from LinkedIn, Indeed, Naukri, and Google Jobs
    if include_job_boards:
        try:
            board_jobs, board_errors = fetch_multi_source_24h(
                location="India",
                hours_old=24,
                results_per_site=10,
            )
            raw_jobs.extend(board_jobs)
            errors.extend(board_errors)
        except Exception as exc:
            LOG.warning("Multi-source 24h job board fetch failed: %s", exc)
            errors.append(f"Multi-source 24h fetch error: {exc}")

    matched_jobs: list[dict[str, Any]] = []
    for job in raw_jobs:
        evaluation = evaluate_job(job, profile)
        if evaluation.get("eligible") or evaluation.get("discovery_candidate"):
            enriched = dict(job)
            enriched.update(evaluation)
            matched_jobs.append(enriched)

    ranked = sort_jobs_bengaluru_first(matched_jobs)
    capped = ranked[: max(1, target)]

    inserted = 0
    duplicates_skipped = 0
    for job in capped:
        res = save_job(
            title=job["title"],
            company=job["company"],
            location=job.get("location", ""),
            url=job.get("url", ""),
            source=job.get("source", "Public ATS"),
            jd=job.get("jd")
            or f"Public posting. Track: {job['track']}; posted: {job.get('posted_at', '')}",
            external_id=job.get("external_id", ""),
            posted_at=job.get("posted_at", ""),
            employment_type=job.get("employment_type", ""),
            track=job.get("track", "Other"),
            match_score=job.get("match_score"),
            eligibility_status=job.get("eligibility_status", "Review required"),
            eligibility_reasons=job.get("eligibility_reasons", []),
        )
        if res["status"] == "inserted":
            inserted += 1
        else:
            duplicates_skipped += 1

    summary_text = build_daily_summary(
        fetched=len(raw_jobs),
        matched=len(ranked),
        inserted=inserted,
        duplicates_skipped=duplicates_skipped,
        expired_marked=expired_marked,
        errors=errors,
        top_jobs=capped,
    )

    record_discovery_run(
        jobs_fetched=len(raw_jobs),
        jobs_matched=len(ranked),
        new_jobs_inserted=inserted,
        duplicates_skipped=duplicates_skipped,
        expired_marked=expired_marked,
        errors=errors,
        summary_text=summary_text,
    )

    return {
        "fetched": len(raw_jobs),
        "matched": len(ranked),
        "inserted": inserted,
        "duplicates_skipped": duplicates_skipped,
        "expired_marked": expired_marked,
        "processed": inserted,  # backward-compatible key
        "errors": errors,
        "summary": summary_text,
        "jobs": capped,
    }