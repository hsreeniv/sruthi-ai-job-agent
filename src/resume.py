from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

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
    # Prioritize skills that appear in the JD without fabricating anything
    prioritized = sorted(
        all_skills,
        key=lambda s: (0 if any(k in s.lower() for k in jd_kws) else 1, s.lower()),
    )

    projects = profile.get("projects", [])
    projects_sorted = sorted(
        projects,
        key=lambda p: -sum(1 for k in jd_kws if k in str(p).lower()),
    )

    role_title = job.get("title") or "Engineering Intern / Fresher"
    company = job.get("company") or "Target Organization"
    summary = (
        (analysis or {}).get("tailored_summary")
        or f"Final-year {profile.get('degree', 'B.Tech ECE')} student ({profile.get('batch', '2023-2027')}) "
           f"targeting {role_title} at {company}. Strong foundation in "
           f"{', '.join(prioritized[:6]) if prioritized else 'Electronics, Embedded Systems, and Python'}."
    )

    return {
        "name": profile.get("name", "SRUTHI M"),
        "contact": " | ".join(
            x for x in [
                profile.get("location", "Bengaluru, Karnataka"),
                profile.get("phone", ""),
                profile.get("email", ""),
                profile.get("linkedin", ""),
                profile.get("github", ""),
            ] if x
        ),
        "summary": summary,
        "education": {
            "degree": profile.get("degree", "B.Tech — Electronics & Communication Engineering"),
            "college": f"{profile.get('college', '')} ({profile.get('university', '')})".strip(" ()"),
            "timeline": f"Batch {profile.get('batch', '2023-2027')} | Graduating {profile.get('graduation_month', 'May 2027')} | {profile.get('backlogs', 'No active backlogs')}",
        },
        "skills": prioritized,
        "experience": profile.get("experience", []) or profile.get("internships", []),
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
        Paragraph(sections["name"], name_style),
        Paragraph(sections["contact"], contact_style),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1")),
        Spacer(1, 4),
        Paragraph("PROFESSIONAL SUMMARY", sec_style),
        Paragraph(sections["summary"], body_style),
        Paragraph("EDUCATION", sec_style),
        Paragraph(f"<b>{sections['education']['degree']}</b> — {sections['education']['college']}", body_style),
        Paragraph(sections["education"]["timeline"], body_style),
    ]

    if sections["skills"]:
        story.append(Paragraph("TECHNICAL SKILLS", sec_style))
        story.append(Paragraph(", ".join(sections["skills"]), body_style))

    if sections["experience"]:
        story.append(Paragraph("INTERNSHIPS &amp; TRAINING", sec_style))
        for exp in sections["experience"]:
            if isinstance(exp, dict):
                line = f"<b>{exp.get('role', exp.get('title', ''))}</b> — {exp.get('company', exp.get('organization', ''))} ({exp.get('duration', '')})"
                story.append(Paragraph(line, body_style))
                if exp.get("description"):
                    story.append(Paragraph(f"• {exp['description']}", body_style))
            else:
                story.append(Paragraph(f"• {exp}", body_style))

    if sections["projects"]:
        story.append(Paragraph("PROJECTS", sec_style))
        for proj in sections["projects"]:
            if isinstance(proj, dict):
                story.append(Paragraph(f"<b>{proj.get('name', proj.get('title', 'Project'))}</b>", body_style))
                desc = proj.get("description") or proj.get("summary") or ""
                if desc:
                    story.append(Paragraph(f"• {desc}", body_style))
            else:
                story.append(Paragraph(f"• {proj}", body_style))

    if sections["certifications"]:
        story.append(Paragraph("CERTIFICATIONS", sec_style))
        for cert in sections["certifications"]:
            story.append(Paragraph(f"• {cert}", body_style))

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

    p_name = doc.add_paragraph()
    p_name.paragraph_format.space_after = Pt(2)
    r_name = p_name.add_run(sections["name"])
    r_name.bold = True
    r_name.font.size = Pt(16)

    p_contact = doc.add_paragraph(sections["contact"])
    p_contact.paragraph_format.space_after = Pt(6)
    for run in p_contact.runs:
        run.font.size = Pt(8.5)

    add_heading_line("PROFESSIONAL SUMMARY")
    doc.add_paragraph(sections["summary"]).runs[0].font.size = Pt(9.5)

    add_heading_line("EDUCATION")
    p_ed = doc.add_paragraph()
    r_ed = p_ed.add_run(f"{sections['education']['degree']} — {sections['education']['college']}")
    r_ed.bold = True
    r_ed.font.size = Pt(9.5)
    p_ed2 = doc.add_paragraph(sections["education"]["timeline"])
    p_ed2.runs[0].font.size = Pt(9)

    if sections["skills"]:
        add_heading_line("TECHNICAL SKILLS")
        doc.add_paragraph(", ".join(sections["skills"])).runs[0].font.size = Pt(9.5)

    if sections["experience"]:
        add_heading_line("INTERNSHIPS & TRAINING")
        for exp in sections["experience"]:
            if isinstance(exp, dict):
                p = doc.add_paragraph()
                r = p.add_run(f"{exp.get('role', exp.get('title', ''))} — {exp.get('company', exp.get('organization', ''))} ({exp.get('duration', '')})")
                r.bold = True
                r.font.size = Pt(9.5)
                if exp.get("description"):
                    doc.add_paragraph(f"• {exp['description']}").runs[0].font.size = Pt(9)
            else:
                doc.add_paragraph(f"• {exp}").runs[0].font.size = Pt(9)

    if sections["projects"]:
        add_heading_line("PROJECTS")
        for proj in sections["projects"]:
            if isinstance(proj, dict):
                p = doc.add_paragraph()
                r = p.add_run(proj.get("name", proj.get("title", "Project")))
                r.bold = True
                r.font.size = Pt(9.5)
                desc = proj.get("description") or proj.get("summary") or ""
                if desc:
                    doc.add_paragraph(f"• {desc}").runs[0].font.size = Pt(9)
            else:
                doc.add_paragraph(f"• {proj}").runs[0].font.size = Pt(9)

    if sections["certifications"]:
        add_heading_line("CERTIFICATIONS")
        for cert in sections["certifications"]:
            doc.add_paragraph(f"• {cert}").runs[0].font.size = Pt(9)

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

    # Return PDF as the primary path used for applying & autofill
    return str(pdf_path), ats_report