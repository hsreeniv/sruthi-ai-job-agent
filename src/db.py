from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("data/job_agent.db")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _get_existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = _get_existing_columns(conn, table)
    for col_name, col_def in columns.items():
        if col_name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")


def init_db() -> None:
    with connect() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dedupe_key TEXT UNIQUE,
                external_id TEXT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                url TEXT,
                source TEXT,
                jd TEXT NOT NULL,
                posted_at TEXT,
                employment_type TEXT,
                track TEXT DEFAULT 'Other',
                match_score INTEGER,
                eligibility_status TEXT DEFAULT 'Review required',
                eligibility_reasons TEXT DEFAULT '[]',
                discovery_date TEXT,
                application_status TEXT DEFAULT 'not_applied',
                status TEXT DEFAULT 'new',
                is_expired INTEGER DEFAULT 0,
                last_seen_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        _ensure_columns(
            c,
            "jobs",
            {
                "external_id": "TEXT",
                "posted_at": "TEXT",
                "employment_type": "TEXT",
                "track": "TEXT DEFAULT 'Other'",
                "eligibility_status": "TEXT DEFAULT 'Review required'",
                "eligibility_reasons": "TEXT DEFAULT '[]'",
                "discovery_date": "TEXT",
                "application_status": "TEXT DEFAULT 'not_applied'",
                "is_expired": "INTEGER DEFAULT 0",
                "last_seen_at": "TEXT",
            },
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                resume_path TEXT,
                answers_json TEXT,
                status TEXT DEFAULT 'draft',
                approved_at TEXT,
                submitted_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS company_directory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT UNIQUE NOT NULL,
                career_url TEXT,
                ats_provider TEXT,
                board_identifier TEXT,
                category TEXT,
                location TEXT,
                connector_status TEXT DEFAULT 'pending_verification',
                enabled INTEGER DEFAULT 0,
                last_successful_fetch TEXT,
                last_error TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS discovery_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TEXT NOT NULL,
                jobs_fetched INTEGER DEFAULT 0,
                jobs_matched INTEGER DEFAULT 0,
                new_jobs_inserted INTEGER DEFAULT 0,
                duplicates_skipped INTEGER DEFAULT 0,
                expired_marked INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                errors_json TEXT DEFAULT '[]',
                summary_text TEXT
            )
            """
        )

        c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company_source ON jobs(company, source)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_eligibility ON jobs(eligibility_status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_discovery_date ON jobs(discovery_date)")


def build_dedupe_key(
    company: str,
    title: str,
    url: str = "",
    jd: str = "",
    external_id: str = "",
    source: str = "",
) -> str:
    clean_company = (company or "").strip().lower()
    clean_title = (title or "").strip().lower()
    clean_source = (source or "").strip().lower()
    clean_ext = (external_id or "").strip().lower()
    clean_url = (url or "").strip().lower().split("?")[0]

    if clean_ext and clean_source:
        raw = f"{clean_source}|{clean_company}|{clean_ext}"
    elif clean_url:
        raw = f"{clean_company}|{clean_title}|{clean_url}"
    else:
        raw = f"{clean_company}|{clean_title}|{(jd or '')[:300].strip().lower()}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def save_job(
    title: str,
    company: str,
    location: str = "",
    url: str = "",
    source: str = "Manual",
    jd: str = "",
    external_id: str = "",
    posted_at: str = "",
    employment_type: str = "",
    track: str = "Other",
    match_score: int | None = None,
    eligibility_status: str = "Review required",
    eligibility_reasons: list[str] | str | None = None,
    application_status: str = "not_applied",
) -> dict[str, Any]:
    """Insert a job if new, or update last_seen_at if duplicate (preserving submitted/dismissed status)."""
    now = utc_now_iso()
    today = now[:10]
    key = build_dedupe_key(
        company=company,
        title=title,
        url=url,
        jd=jd,
        external_id=external_id,
        source=source,
    )

    if isinstance(eligibility_reasons, list):
        reasons_json = json.dumps(eligibility_reasons, ensure_ascii=False)
    elif isinstance(eligibility_reasons, str):
        reasons_json = eligibility_reasons
    else:
        reasons_json = "[]"

    with connect() as c:
        existing = c.execute(
            "SELECT id FROM jobs WHERE dedupe_key = ?", (key,)
        ).fetchone()

        if existing:
            c.execute(
                """
                UPDATE jobs
                SET last_seen_at = ?, is_expired = 0
                WHERE id = ?
                """,
                (now, existing["id"]),
            )
            return {"status": "duplicate", "job_id": existing["id"], "dedupe_key": key}

        cur = c.execute(
            """
            INSERT INTO jobs (
                dedupe_key, external_id, title, company, location, url, source, jd,
                posted_at, employment_type, track, match_score,
                eligibility_status, eligibility_reasons, discovery_date,
                application_status, status, is_expired, last_seen_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', 0, ?, ?)
            """,
            (
                key,
                str(external_id or "").strip(),
                title.strip(),
                company.strip(),
                (location or "").strip(),
                (url or "").strip(),
                (source or "Manual").strip(),
                jd or "",
                (posted_at or "").strip(),
                (employment_type or "").strip(),
                track or "Other",
                match_score,
                eligibility_status or "Review required",
                reasons_json,
                today,
                application_status or "not_applied",
                now,
                now,
            ),
        )
        return {"status": "inserted", "job_id": cur.lastrowid, "dedupe_key": key}


def dismiss_job(job_id: int, reason_status: str = "dismissed") -> None:
    """Hide a job from active views while keeping its dedupe_key so future runs never re-add it."""
    with connect() as c:
        c.execute(
            "UPDATE jobs SET application_status = ? WHERE id = ?",
            (reason_status, job_id),
        )


def mark_missing_jobs_expired(company: str, source: str, active_dedupe_keys: set[str]) -> int:
    """Mark previously active jobs from a successfully fetched board as expired if absent."""
    with connect() as c:
        rows = c.execute(
            """
            SELECT id, dedupe_key FROM jobs
            WHERE company = ? AND source = ? AND is_expired = 0
            """,
            (company, source),
        ).fetchall()

        expired_ids = [r["id"] for r in rows if r["dedupe_key"] not in active_dedupe_keys]
        if not expired_ids:
            return 0

        placeholders = ",".join("?" for _ in expired_ids)
        c.execute(f"UPDATE jobs SET is_expired = 1 WHERE id IN ({placeholders})", expired_ids)
        return len(expired_ids)


def update_job_analysis(
    job_id: int,
    match_score: int | None = None,
    track: str | None = None,
    eligibility_status: str | None = None,
    eligibility_reasons: list[str] | None = None,
) -> None:
    with connect() as c:
        c.execute(
            """
            UPDATE jobs
            SET match_score = COALESCE(?, match_score),
                track = COALESCE(?, track),
                eligibility_status = COALESCE(?, eligibility_status),
                eligibility_reasons = COALESCE(?, eligibility_reasons)
            WHERE id = ?
            """,
            (
                match_score,
                track,
                eligibility_status,
                json.dumps(eligibility_reasons, ensure_ascii=False)
                if eligibility_reasons is not None
                else None,
                job_id,
            ),
        )


def list_jobs(include_expired: bool = False, include_applied: bool = False) -> list[dict[str, Any]]:
    """Return active jobs, automatically excluding submitted/applied/dismissed roles."""
    with connect() as c:
        clauses: list[str] = []
        if not include_expired:
            clauses.append("COALESCE(is_expired, 0) = 0")
        if not include_applied:
            clauses.append("COALESCE(application_status, 'not_applied') NOT IN ('submitted', 'applied', 'dismissed')")
            clauses.append(
                "id NOT IN (SELECT job_id FROM applications WHERE status IN ('submitted', 'applied'))"
            )
        query = "SELECT * FROM jobs"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC"
        rows = c.execute(query).fetchall()
        return [dict(r) for r in rows]


def list_applications() -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            """
            SELECT a.id, a.job_id, j.company, j.title, a.status, a.resume_path,
                   a.approved_at, a.submitted_at, a.created_at
            FROM applications a
            JOIN jobs j ON j.id = a.job_id
            ORDER BY a.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_company_status(
    company_name: str,
    career_url: str = "",
    ats_provider: str = "",
    board_identifier: str = "",
    category: str = "",
    location: str = "",
    connector_status: str = "pending_verification",
    enabled: bool = False,
    last_successful_fetch: str | None = None,
    last_error: str | None = None,
) -> None:
    now = utc_now_iso()
    with connect() as c:
        c.execute(
            """
            INSERT INTO company_directory (
                company_name, career_url, ats_provider, board_identifier,
                category, location, connector_status, enabled,
                last_successful_fetch, last_error, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_name) DO UPDATE SET
                career_url = excluded.career_url,
                ats_provider = excluded.ats_provider,
                board_identifier = excluded.board_identifier,
                category = excluded.category,
                location = excluded.location,
                connector_status = excluded.connector_status,
                enabled = excluded.enabled,
                last_successful_fetch = COALESCE(excluded.last_successful_fetch, company_directory.last_successful_fetch),
                last_error = excluded.last_error,
                updated_at = excluded.updated_at
            """,
            (
                company_name,
                career_url,
                ats_provider,
                board_identifier,
                category,
                location,
                connector_status,
                1 if enabled else 0,
                last_successful_fetch,
                last_error,
                now,
            ),
        )


def list_company_directory() -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM company_directory ORDER BY enabled DESC, company_name ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def record_discovery_run(
    jobs_fetched: int,
    jobs_matched: int,
    new_jobs_inserted: int,
    duplicates_skipped: int,
    expired_marked: int,
    errors: list[str],
    summary_text: str = "",
) -> int:
    with connect() as c:
        cur = c.execute(
            """
            INSERT INTO discovery_runs (
                run_at, jobs_fetched, jobs_matched, new_jobs_inserted,
                duplicates_skipped, expired_marked, error_count, errors_json, summary_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                utc_now_iso(),
                jobs_fetched,
                jobs_matched,
                new_jobs_inserted,
                duplicates_skipped,
                expired_marked,
                len(errors),
                json.dumps(errors, ensure_ascii=False),
                summary_text,
            ),
        )
        return int(cur.lastrowid)


def list_discovery_runs(limit: int = 10) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM discovery_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]