from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from src.ats_scorer import extract_jd_keywords, score_resume_against_jd

OUTPUT_DIR = Path("output/resumes")
NAVY = RGBColor(0x1B, 0x36, 0x5D)
DARK = RGBColor(0x22, 0x22, 0x22)
MUTED = RGBColor(0x55, 0x55, 0x55)


def _safe_filename(text: str, max_len: int = 32) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")
    return (cleaned or "Role")[:max_len]


def _add_bottom_border(paragraph, color_hex: str = "1B365D", size: str = "6") -> None:
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color_hex)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_section_heading(doc: Document, title: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(1.5)
    p.paragraph_format.line_spacing = 1.03
    p.paragraph_format.keep_with_next = True
    run = p.add_run(title.upper())
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(10)
    run.font.color.rgb = NAVY
    _add_bottom_border(p)


def _add_dated_header(doc: Document, left_text: str, right_text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(0.5)
    p.paragraph_format.line_spacing = 1.03
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.tab_stops.add_tab_stop(Inches(7.5), WD_TAB_ALIGNMENT.RIGHT)

    r_left = p.add_run(left_text)
    r_left.bold = True
    r_left.font.name = "Calibri"
    r_left.font.size = Pt(9.2)
    r_left.font.color.rgb = DARK

    if right_text:
        r_right = p.add_run(f"\t{right_text}")
        r_right.bold = True
        r_right.font.name = "Calibri"
        r_right.font.size = Pt(8.8)
        r_right.font.color.rgb = MUTED


def _add_body(doc: Document, text: str, italic: bool = False, color: RGBColor = DARK, space_after: float = 1.0) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.03
    run = p.add_run(text)
    run.italic = italic
    run.font.name = "Calibri"
    run.font.size = Pt(8.8)
    run.font.color.rgb = color


def _add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.16)
    p.paragraph_format.first_line_indent = Inches(-0.11)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0.8)
    p.paragraph_format.line_spacing = 1.03
    run = p.add_run(f"•  {text}")
    run.font.name = "Calibri"
    run.font.size = Pt(8.8)
    run.font.color.rgb = DARK


def _prioritize_skill_group_items(group_text: str, jd_keywords: list[str]) -> tuple[int, str]:
    """Reorder verified skills inside a skill group so JD-matching items appear first."""
    if not jd_keywords:
        return 0, group_text

    clauses = [c.strip() for c in group_text.split(";") if c.strip()]
    total_hits = 0
    reordered_clauses: list[str] = []

    for clause in clauses:
        prefix = ""
        body = clause
        if ":" in clause:
            prefix, body = clause.split(":", 1)
            prefix = prefix.strip() + ": "
            body = body.strip()

        items = [i.strip() for i in body.split(",") if i.strip()]
        scored_items: list[tuple[int, int, str]] = []
        for idx, item in enumerate(items):
            item_low = item.lower()
            hits = sum(1 for kw in jd_keywords if kw in item_low)
            total_hits += hits
            scored_items.append((hits, -idx, item))

        scored_items.sort(reverse=True)
        reordered_body = ", ".join(item for _, _, item in scored_items)
        reordered_clauses.append(f"{prefix}{reordered_body}")

    return total_hits, "; ".join(reordered_clauses)


def _score_entry_overlap(entry: dict[str, Any], jd_keywords: list[str], preferred_track: str) -> tuple[int, int]:
    blob = " ".join(
        [
            entry.get("title", ""),
            entry.get("subtitle", ""),
            " ".join(entry.get("bullets", [])),
        ]
    ).lower()
    kw_hits = sum(1 for kw in jd_keywords if kw in blob)
    track_bonus = 1 if entry.get("track") == preferred_track else 0
    return (kw_hits, track_bonus)


def create_tailored_resume_with_ats(
    profile: dict[str, Any],
    analysis: dict[str, Any] | None,
    job: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Generate a single-page, JD-tailored .docx resume (zero fabrication) and return (path, ats_report)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    analysis = analysis or {}
    track = analysis.get("track") or job.get("track") or "Core Engineering"
    is_it = track == "IT"
    preferred_track = "IT" if is_it else "Core Engineering"

    jd_keywords = extract_jd_keywords(job.get("jd", ""), job.get("title", ""), analysis)

    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.35)
        section.bottom_margin = Inches(0.35)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

    # Header: Name, Headline, Contact
    p_name = doc.add_paragraph()
    p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_name.paragraph_format.space_before = Pt(0)
    p_name.paragraph_format.space_after = Pt(0.5)
    p_name.paragraph_format.line_spacing = 1.0
    r_name = p_name.add_run(profile.get("name", "SRUTHI M"))
    r_name.bold = True
    r_name.font.name = "Calibri"
    r_name.font.size = Pt(15)
    r_name.font.color.rgb = NAVY

    headline = profile.get("headline_it") if is_it else profile.get("headline_core")
    if headline:
        p_head = doc.add_paragraph()
        p_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_head.paragraph_format.space_before = Pt(0)
        p_head.paragraph_format.space_after = Pt(0.5)
        p_head.paragraph_format.line_spacing = 1.0
        r_head = p_head.add_run(headline)
        r_head.bold = True
        r_head.font.name = "Calibri"
        r_head.font.size = Pt(9.2)
        r_head.font.color.rgb = DARK

    p_contact = doc.add_paragraph()
    p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_contact.paragraph_format.space_before = Pt(0)
    p_contact.paragraph_format.space_after = Pt(2.5)
    p_contact.paragraph_format.line_spacing = 1.0
    r_contact = p_contact.add_run(profile.get("contact_line", ""))
    r_contact.font.name = "Calibri"
    r_contact.font.size = Pt(8.8)
    r_contact.font.color.rgb = MUTED

    # 1. Professional Summary
    _add_section_heading(doc, "Professional Summary")
    summary = (
        profile.get("summary_it")
        if is_it and profile.get("summary_it")
        else profile.get("summary_core") or profile.get("summary", "")
    )
    _add_body(doc, summary, space_after=1.5)

    # 2. Education
    _add_section_heading(doc, "Education")
    for edu in profile.get("education", []):
        _add_dated_header(doc, edu.get("degree", ""), edu.get("dates", ""))
        if edu.get("institution"):
            _add_body(doc, edu["institution"], italic=True, color=MUTED, space_after=0.5)
        if edu.get("details"):
            _add_body(doc, edu["details"], space_after=1.2)

    # 3. Technical Skills (dynamically prioritized by JD keyword matches)
    _add_section_heading(doc, "Technical Skills")
    skill_groups: dict[str, str] = profile.get("skill_groups", {})
    default_order = (
        ["Languages", "Software & Tools", "Embedded Systems", "Core Electronics & VLSI", "Protocols"]
        if is_it
        else ["Core Electronics & VLSI", "Embedded Systems", "Protocols", "Languages", "Software & Tools"]
    )

    ranked_groups: list[tuple[int, int, str, str]] = []
    for idx, group_name in enumerate(default_order):
        if group_name in skill_groups:
            hits, reordered_text = _prioritize_skill_group_items(skill_groups[group_name], jd_keywords)
            ranked_groups.append((hits, -idx, group_name, reordered_text))

    ranked_groups.sort(reverse=True)

    for _, _, group_name, group_text in ranked_groups:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0.8)
        p.paragraph_format.line_spacing = 1.03
        r_k = p.add_run(f"{group_name}: ")
        r_k.bold = True
        r_k.font.name = "Calibri"
        r_k.font.size = Pt(8.8)
        r_k.font.color.rgb = DARK
        r_v = p.add_run(group_text)
        r_v.font.name = "Calibri"
        r_v.font.size = Pt(8.8)
        r_v.font.color.rgb = DARK

    # 4. Internships & Training
    _add_section_heading(doc, "Internships & Training")
    internships = sorted(
        list(profile.get("internship", [])),
        key=lambda x: _score_entry_overlap(x, jd_keywords, preferred_track),
        reverse=True,
    )
    for item in internships:
        _add_dated_header(doc, item.get("title", item.get("name", "")), item.get("dates", ""))
        if item.get("subtitle"):
            _add_body(doc, item["subtitle"], italic=True, color=MUTED, space_after=0.5)
        for b in item.get("bullets", []):
            _add_bullet(doc, b)

    # 5. Projects
    _add_section_heading(doc, "Projects")
    projects = sorted(
        list(profile.get("projects", [])),
        key=lambda x: _score_entry_overlap(x, jd_keywords, preferred_track),
        reverse=True,
    )
    for proj in projects:
        _add_dated_header(doc, proj.get("title", proj.get("name", "")), proj.get("dates", ""))
        if proj.get("subtitle"):
            _add_body(doc, proj["subtitle"], italic=True, color=MUTED, space_after=0.5)
        for b in proj.get("bullets", []):
            _add_bullet(doc, b)

    # 6. Certifications
    certs = profile.get("certifications", [])
    if certs:
        _add_section_heading(doc, "Certifications")
        for c in certs:
            _add_bullet(doc, c)

    # 7. Achievements
    achievements = profile.get("achievements", [])
    if achievements:
        _add_section_heading(doc, "Achievements")
        for a in achievements:
            _add_bullet(doc, a)

    company_slug = _safe_filename(job.get("company", "Company"), 24)
    title_slug = _safe_filename(job.get("title", "Role"), 32)
    out_path = OUTPUT_DIR / f"Sruthi_M_{company_slug}_{title_slug}.docx"
    doc.save(out_path)

    ats_report = score_resume_against_jd(out_path, job, analysis)
    return str(out_path), ats_report


def create_tailored_resume(
    profile: dict[str, Any],
    analysis: dict[str, Any] | None,
    job: dict[str, Any],
) -> str:
    """Backward-compatible wrapper returning only the .docx path."""
    path, _ = create_tailored_resume_with_ats(profile, analysis, job)
    return path