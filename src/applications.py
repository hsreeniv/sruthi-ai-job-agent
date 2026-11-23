from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.db import connect, utc_now_iso
from src.gemini_service import prepare_screening_answers
from src.resume import create_tailored_resume_with_ats

LOG = logging.getLogger(__name__)

DEFAULT_SCREENING_QUESTIONS = [
    "What is your highest degree, branch, and expected graduation date?",
    "Do you have any active backlogs?",
    "Are you available to work in Bengaluru or relocate within India?",
    "Summarize your verified technical skills and internship experience relevant to this role.",
]


def convert_docx_to_pdf(docx_path: str | Path) -> str | None:
    """Convert a .docx resume to PDF if MS Word (docx2pdf) or LibreOffice is available.

    Returns the PDF path string on success, or None if no local converter is installed.
    """
    src = Path(docx_path).resolve()
    pdf_path = src.with_suffix(".pdf")

    # 1. Try docx2pdf (uses Microsoft Word on Windows if installed)
    try:
        from docx2pdf import convert  # type: ignore

        convert(str(src), str(pdf_path))
        if pdf_path.exists():
            return str(pdf_path)
    except Exception as exc:
        LOG.debug("docx2pdf conversion skipped: %s", exc)

    # 2. Try LibreOffice headless if installed
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(src.parent), str(src)],
                check=True,
                capture_output=True,
                timeout=60,
            )
            if pdf_path.exists():
                return str(pdf_path)
        except Exception as exc:
            LOG.debug("LibreOffice PDF conversion skipped: %s", exc)

    return None


def prepare_application_package(
    job: dict[str, Any],
    profile: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    questions: list[str] | None = None,
    use_gemini_answers: bool = True,
) -> dict[str, Any]:
    """Generate tailored resume + ATS score + screening answers and save as 'awaiting_approval'."""
    analysis = analysis or {}
    docx_path, ats_report = create_tailored_resume_with_ats(profile, analysis, job)
    pdf_path = convert_docx_to_pdf(docx_path)
    final_resume_path = pdf_path or docx_path

    q_list = list(questions or [])
    if not q_list:
        q_list = list(analysis.get("screening_questions_to_confirm") or [])
    if not q_list:
        q_list = list(DEFAULT_SCREENING_QUESTIONS)

    answers_payload: dict[str, Any]
    if use_gemini_answers:
        try:
            answers_payload = prepare_screening_answers(job, profile, q_list)
        except Exception as exc:
            LOG.warning("Gemini screening answer prep failed, falling back to placeholders: %s", exc)
            answers_payload = {
                "answers": [
                    {
                        "question": q,
                        "draft_answer": "[VERIFY WITH SRUTHI] Fill using verified profile details.",
                        "needs_verification": True,
                    }
                    for q in q_list
                ]
            }
    else:
        answers_payload = {
            "answers": [
                {
                    "question": q,
                    "draft_answer": "[VERIFY WITH SRUTHI] Fill using verified profile details.",
                    "needs_verification": True,
                }
                for q in q_list
            ]
        }

    now = utc_now_iso()
    answers_payload["ats_report"] = ats_report
    answers_json = json.dumps(answers_payload, ensure_ascii=False)

    with connect() as c:
        existing = c.execute(
            "SELECT id FROM applications WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job["id"],),
        ).fetchone()

        if existing:
            app_id = int(existing["id"])
            c.execute(
                """
                UPDATE applications
                SET resume_path = ?, answers_json = ?, status = 'awaiting_approval'
                WHERE id = ?
                """,
                (final_resume_path, answers_json, app_id),
            )
        else:
            cur = c.execute(
                """
                INSERT INTO applications (job_id, resume_path, answers_json, status, created_at)
                VALUES (?, ?, ?, 'awaiting_approval', ?)
                """,
                (job["id"], final_resume_path, answers_json, now),
            )
            app_id = int(cur.lastrowid)

        c.execute(
            "UPDATE jobs SET application_status = 'awaiting_approval' WHERE id = ?",
            (job["id"],),
        )

    return {
        "application_id": app_id,
        "job_id": job["id"],
        "resume_docx": docx_path,
        "resume_pdf": pdf_path,
        "resume_path": final_resume_path,
        "ats_report": ats_report,
        "answers": answers_payload,
        "status": "awaiting_approval",
    }


def list_applications_detailed() -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            """
            SELECT a.id, a.job_id, j.company, j.title, j.location, j.url, j.source,
                   j.eligibility_status, j.match_score,
                   a.resume_path, a.answers_json, a.status,
                   a.approved_at, a.submitted_at, a.created_at
            FROM applications a
            JOIN jobs j ON j.id = a.job_id
            ORDER BY a.id DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def update_application_answers(app_id: int, answers_payload: dict[str, Any]) -> None:
    with connect() as c:
        c.execute(
            "UPDATE applications SET answers_json = ? WHERE id = ?",
            (json.dumps(answers_payload, ensure_ascii=False), app_id),
        )


def approve_application(app_id: int) -> None:
    """Explicit candidate approval gate. Required before any submission."""
    now = utc_now_iso()
    with connect() as c:
        row = c.execute("SELECT job_id FROM applications WHERE id = ?", (app_id,)).fetchone()
        if not row:
            raise ValueError(f"Application {app_id} not found.")
        c.execute(
            "UPDATE applications SET status = 'approved', approved_at = ? WHERE id = ?",
            (now, app_id),
        )
        c.execute(
            "UPDATE jobs SET application_status = 'approved' WHERE id = ?",
            (row["job_id"],),
        )


def reject_application(app_id: int) -> None:
    with connect() as c:
        row = c.execute("SELECT job_id FROM applications WHERE id = ?", (app_id,)).fetchone()
        if not row:
            raise ValueError(f"Application {app_id} not found.")
        c.execute("UPDATE applications SET status = 'rejected' WHERE id = ?", (app_id,))
        c.execute(
            "UPDATE jobs SET application_status = 'rejected' WHERE id = ?",
            (row["job_id"],),
        )


def mark_application_submitted(app_id: int) -> None:
    """Mark an application submitted ONLY if it has already been explicitly approved."""
    now = utc_now_iso()
    with connect() as c:
        row = c.execute(
            "SELECT job_id, status FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Application {app_id} not found.")
        if row["status"] != "approved":
            raise PermissionError(
                "APPROVAL REQUIRED: Application must be explicitly approved by Sruthi before marking submitted."
            )
        c.execute(
            "UPDATE applications SET status = 'submitted', submitted_at = ? WHERE id = ?",
            (now, app_id),
        )
        c.execute(
            "UPDATE jobs SET application_status = 'submitted' WHERE id = ?",
            (row["job_id"],),
        )