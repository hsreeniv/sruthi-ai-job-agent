from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

RESUMES_DIR = Path("data/resumes")
RESUMES_DIR.mkdir(parents=True, exist_ok=True)

TECH_KEYWORDS = [
    "verilog", "systemverilog", "vlsi", "rtl", "fpga", "asic", "digital", "cmos",
    "embedded", "firmware", "microcontroller", "arm", "stm32", "esp32", "arduino",
    "rtos", "i2c", "spi", "uart", "can", "pcb", "matlab", "simulink", "vivado",
    "cadence", "synopsys", "c", "c++", "python", "java", "sql", "mysql", "linux",
    "git", "github", "docker", "aws", "machine learning", "ai", "opencv", "iot",
    "selenium", "playwright", "testing", "qa", "automation", "rest", "api", "html",
    "css", "javascript", "data structures", "algorithms", "networking", "tcp/ip",
]


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "role").strip()).strip("_")
    return cleaned[:40] or "role"


def _esc(text: str) -> str:
    return escape(str(text or ""))


def _extract_jd_keywords(jd_text: str) -> list[str]:
    lower = (jd_text or "").lower()
    found = []
    for kw in TECH_KEYWORDS:
        if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", lower):
            found.append(kw)
    return found


def _flatten_profile_skills(profile: dict) -> list[str]:
    skills = profile.get("skills", [])
    if isinstance(skills, dict):
        flat = []
        for vals in skills.values():
            if isinstance(vals, list):
                flat.extend(str(v) for v in vals)
            elif vals:
                flat.append(str(vals))
        return flat
    if isinstance(skills, list):
        return [str(s) for s in skills]
    return []


def _extract_bullets(item: dict) -> list[str]:
    """Extracts bullet points regardless of key name in profile.json."""
    for key in ("bullets", "highlights", "points", "details", "responsibilities"):
        val = item.get(key)
        if isinstance(val, list) and val:
            return [str(x).strip() for x in val if str(x).strip()]
    for key in ("description", "summary"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return [val.strip()]
    return []


def _clean_role_target(job: dict) -> str:
    """Prevents noisy scraped web titles (like conference alerts) from entering the summary."""
    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    bad_signals = ("conference", "alert", "blog", "news", "list of", "top 10", "jobs in ")
    if not title or len(title) > 70 or any(b in title.lower() for b in bad_signals):
        track = (job.get("track") or "").lower()
        return "Core Electronics / Embedded & VLSI Engineering" if "core" in track else "Software & Engineering"
    if company and company.lower() not in title.lower() and len(company) <= 35:
        return f"{title} at {company}"
    return title


def _compute_ats_report(resume_text: str, jd_text: str) -> dict:
    jd_kws = _extract_jd_keywords(jd_text)
    res_lower = resume_text.lower()
    matched = [kw for kw in jd_kws if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", res_lower)]
    missing = [kw for kw in jd_kws if kw not in matched]

    match_pct = int(round((len(matched) / len(jd_kws)) * 100)) if jd_kws else 80
    words = len(resume_text.split())
    length_bonus = 15 if 220 <= words <= 650 else 8
    ats_score = min(100, int(round(match_pct * 0.85 + length_bonus)))

    if ats_score >= 85:
        grade = "Excellent"
    elif ats_score >= 70:
        grade = "Strong"
    elif ats_score >= 55:
        grade = "Moderate"
    else:
        grade = "Needs Review"

    return {
        "ats_score": ats_score,
        "grade": grade,
        "keyword_match_pct": match_pct,
        "word_count": words,
        "matched_keywords": matched,
        "missing_keywords": missing[:12],
    }


def _build_tailored_sections(profile: dict, analysis: dict | None, job: dict) -> dict:
    jd_text = f"{job.get('title', '')}\n{job.get('jd', '')}"
    jd_kws = set(_extract_jd_keywords(jd_text))

    all_skills = _flatten_profile_skills(profile)
    prioritized = sorted(
        all_skills,
        key=lambda s: (0 if any(k in s.lower() for k in jd_kws) else 1, s.lower()),
    )

    projects = profile.get("projects", [])
    projects_sorted = sorted(
        projects,
        key=lambda p: -sum(1 for k in jd_kws if k in str(p).lower()),
    )

    c = profile.get("contact") if isinstance(profile.get("contact"), dict) else {}
    contact_parts = [
        profile.get("location") or c.get("location") or "Bengaluru, Karnataka",
        profile.get("phone") or c.get("phone") or "",
        profile.get("email") or c.get("email") or "",
        profile.get("linkedin") or c.get("linkedin") or "",
        profile.get("github") or c.get("github") or "",
    ]

    experience = (
        profile.get("experience")
        or profile.get("internships")
        or profile.get("training")
        or profile.get("internships_and_training")
        or []
    )

    role_target = _clean_role_target(job)
    summary = (
        (analysis or {}).get("tailored_summary")
        or f"Final-year {profile.get('degree', 'B.Tech ECE')} student ({profile.get('batch', '2023-2027')}) "
           f"targeting {role_target} roles. Hands-on foundation in "
           f"{', '.join(prioritized[:7]) if prioritized else 'Embedded C, VLSI/RTL, and Python'}."
    )

    return {
        "name": profile.get("name", "SRUTHI M"),
        "contact": " | ".join(str(x).strip() for x in contact_parts if str(x).strip()),
        "summary": summary,
        "education": {
            "degree": profile.get("degree", "B.Tech — Electronics & Communication Engineering"),
            "college": f"{profile.get('college', '')} ({profile.get('university', '')})".strip(" ()"),
            "timeline": f"Batch {profile.get('batch', '2023-2027')} | Graduating {profile.get('graduation_month', 'May 2027')} | {profile.get('backlogs', 'No active backlogs')}",
        },
        "skills": prioritized,
        "experience": experience,
        "projects": projects_sorted[:4],
        "certifications": profile.get("certifications", []),
    }


def _write_pdf(sections: dict, pdf_path: Path) -> None:
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )
    styles = getSampleStyleSheet()
    name_style = ParagraphStyle("Name", parent=styles["Heading1"], fontSize=16, leading=19, textColor=colors.HexColor("#0f172a"), spaceAfter=2)
    contact_style = ParagraphStyle("Contact", parent=styles["Normal"], fontSize=8.5, leading=11, textColor=colors.HexColor("#475569"), spaceAfter=6)
    sec_style = ParagraphStyle("Sec", parent=styles["Heading2"], fontSize=10.5, leading=13, textColor=colors.HexColor("#1e3a8a"), spaceBefore=7, spaceAfter=3)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9.2, leading=12.5, textColor=colors.HexColor("#1e293b"), spaceAfter=3)

    story = [
        Paragraph(_esc(sections["name"]), name_style),
        Paragraph(_esc(sections["contact"]), contact_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1")),
        Spacer(1, 4),
        Paragraph("PROFESSIONAL SUMMARY", sec_style),
        Paragraph(_esc(sections["summary"]), body_style),
        Paragraph("EDUCATION", sec_style),
        Paragraph(f"<b>{_esc(sections['education']['degree'])}</b> — {_esc(sections['education']['college'])}", body_style),
        Paragraph(_esc(sections["education"]["timeline"]), body_style),
    ]

    if sections["skills"]:
        story.append(Paragraph("TECHNICAL SKILLS", sec_style))
        story.append(Paragraph(_esc(", ".join(sections["skills"])), body_style))

    if sections["experience"]:
        story.append(Paragraph("INTERNSHIPS &amp; TRAINING", sec_style))
        for exp in sections["experience"]:
            if isinstance(exp, dict):
                role = _esc(exp.get("role") or exp.get("title") or "")
                org = _esc(exp.get("company") or exp.get("organization") or "")
                dur = _esc(exp.get("duration") or "")
                dur_part = f" ({dur})" if dur else ""
                story.append(Paragraph(f"<b>{role}</b> — {org}{dur_part}", body_style))
                for b in _extract_bullets(exp):
                    story.append(Paragraph(f"• {_esc(b)}", body_style))
            else:
                story.append(Paragraph(f"• {_esc(exp)}", body_style))

    if sections["projects"]:
        story.append(Paragraph("PROJECTS", sec_style))
        for proj in sections["projects"]:
            if isinstance(proj, dict):
                title = _esc(proj.get("name") or proj.get("title") or "Project")
                tech = f" ({_esc(', '.join(proj['tech']))})" if isinstance(proj.get("tech"), list) and proj.get("tech") else ""
                story.append(Paragraph(f"<b>{title}</b>{tech}", body_style))
                for b in _extract_bullets(proj):
                    story.append(Paragraph(f"• {_esc(b)}", body_style))
            else:
                story.append(Paragraph(f"• {_esc(proj)}", body_style))

    if sections["certifications"]:
        story.append(Paragraph("CERTIFICATIONS", sec_style))
        for cert in sections["certifications"]:
            story.append(Paragraph(f"• {_esc(cert)}", body_style))

    doc.build(story)


def _write_docx(sections: dict, docx_path: Path) -> None:
    doc = Document()
    for sec in doc.sections:
        sec.top_margin = Inches(0.5)
        sec.bottom_margin = Inches(0.5)
        sec.left_margin = Inches(0.6)
        sec.right_margin = Inches(0.6)

    def add_heading_line(text: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(7)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(text)
        r.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)

    def add_body_line(text: str, size: float = 9.5) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(text)
        r.font.size = Pt(size)

    p_name = doc.add_paragraph()
    p_name.paragraph_format.space_after = Pt(2)
    r_name = p_name.add_run(sections["name"])
    r_name.bold = True
    r_name.font.size = Pt(16)

    add_body_line(sections["contact"], size=8.5)

    add_heading_line("PROFESSIONAL SUMMARY")
    add_body_line(sections["summary"], size=9.5)

    add_heading_line("EDUCATION")
    p_ed = doc.add_paragraph()
    p_ed.paragraph_format.space_after = Pt(1)
    r_ed = p_ed.add_run(f"{sections['education']['degree']} — {sections['education']['college']}")
    r_ed.bold = True
    r_ed.font.size = Pt(9.5)
    add_body_line(sections["education"]["timeline"], size=9.0)

    if sections["skills"]:
        add_heading_line("TECHNICAL SKILLS")
        add_body_line(", ".join(sections["skills"]), size=9.5)

    if sections["experience"]:
        add_heading_line("INTERNSHIPS & TRAINING")
        for exp in sections["experience"]:
            if isinstance(exp, dict):
                role = exp.get("role") or exp.get("title") or ""
                org = exp.get("company") or exp.get("organization") or ""
                dur = exp.get("duration") or ""
                dur_part = f" ({dur})" if dur else ""
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                r = p.add_run(f"{role} — {org}{dur_part}")
                r.bold = True
                r.font.size = Pt(9.5)
                for b in _extract_bullets(exp):
                    add_body_line(f"• {b}", size=9.0)
            else:
                add_body_line(f"• {exp}", size=9.0)

    if sections["projects"]:
        add_heading_line("PROJECTS")
        for proj in sections["projects"]:
            if isinstance(proj, dict):
                title = proj.get("name") or proj.get("title") or "Project"
                tech = f" ({', '.join(proj['tech'])})" if isinstance(proj.get("tech"), list) and proj.get("tech") else ""
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                r = p.add_run(f"{title}{tech}")
                r.bold = True
                r.font.size = Pt(9.5)
                for b in _extract_bullets(proj):
                    add_body_line(f"• {b}", size=9.0)
            else:
                add_body_line(f"• {proj}", size=9.0)

    if sections["certifications"]:
        add_heading_line("CERTIFICATIONS")
        for cert in sections["certifications"]:
            add_body_line(f"• {cert}", size=9.0)

    doc.save(str(docx_path))


def create_tailored_resume_with_ats(profile: dict, analysis: dict | None, job: dict) -> tuple[str, dict]:
    """Generates both PDF (for applying) and DOCX (for editing) and returns (pdf_path, ats_report)."""
    sections = _build_tailored_sections(profile, analysis, job)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"Sruthi_{_slugify(job.get('company', 'Company'))}_{_slugify(job.get('title', 'Role'))}_{stamp}"

    pdf_path = RESUMES_DIR / f"{base_name}.pdf"
    docx_path = RESUMES_DIR / f"{base_name}.docx"

    _write_pdf(sections, pdf_path)
    _write_docx(sections, docx_path)

    plain_text = " ".join(
        [
            sections["name"],
            sections["summary"],
            " ".join(sections["skills"]),
            str(sections["experience"]),
            str(sections["projects"]),
            str(sections["certifications"]),
        ]
    )
    ats_report = _compute_ats_report(plain_text, f"{job.get('title', '')}\n{job.get('jd', '')}")
    ats_report["pdf_path"] = str(pdf_path)
    ats_report["docx_path"] = str(docx_path)

    return str(pdf_path), ats_report