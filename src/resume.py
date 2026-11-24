from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

RESUMES_DIR = Path("data/resumes")
RESUMES_DIR.mkdir(parents=True, exist_ok=True)

TECH_KEYWORDS = [
    "verilog", "systemverilog", "vlsi", "rtl", "fpga", "asic", "digital", "cmos", "fsm",
    "embedded", "firmware", "microcontroller", "arm", "stm32", "esp32", "arduino",
    "rtos", "i2c", "spi", "uart", "can", "pcb", "matlab", "simulink", "modelsim",
    "testbench", "verification", "timing", "c", "c++", "python", "java", "sql",
    "linux", "git", "github", "machine learning", "ai", "opencv", "numpy", "matplotlib",
    "scikit-learn", "data structures", "algorithms", "data analytics", "software",
]

MASTER_DEFAULTS = {
    "name": "SRUTHI M",
    "phone": "+91 9014771797",
    "email": "shrutimurugesh@gmail.com",
    "location": "Kuppam, Andhra Pradesh",
    "education": [
        {
            "title": "B.Tech — Electronics & Communication Engineering",
            "dates": "Sep 2023 – May 2027",
            "subtitle": "Aditya College of Engineering, Madanapalle | JNTU Anantapur | CGPA: 7.5/10",
            "extra": "Coursework: Digital Electronics, Microprocessors & Microcontrollers, Signals & Systems, Data Structures & Algorithms (C), Linear Algebra & Probability",
        },
        {
            "title": "Intermediate (Class XII) — MPC",
            "dates": "2021 – 2023",
            "subtitle": "Sri Chaitanya Junior College, Tirupathi | Score: 90.3%",
            "extra": "",
        },
    ],
    "skill_categories": [
        ("Languages", "C (Proficient), Python (Intermediate), Embedded C (Familiar), Java (Basic)"),
        ("Software & Tools", "Git, GitHub, Linux, Windows, Jupyter Notebook, Google Workspace; Python libraries: NumPy, scikit-learn, OpenCV, Matplotlib"),
        ("Embedded Systems", "Embedded C, Arduino UNO / Arduino IDE, microcontrollers, hardware interrupts, 7-segment display multiplexing"),
        ("Core Electronics & VLSI", "RTL design concepts, digital logic design, FSMs, functional verification, testbench development, timing analysis, ModelSim (conceptual), MATLAB"),
        ("Protocols", "UART, SPI, I2C (academic coursework)"),
    ],
    "internships": [
        {
            "track": "core",
            "title": "VLSI Design & Verification Training — VLSI Guru Institute, Bengaluru",
            "dates": "May 2025 – Jul 2025",
            "subtitle": "Offline Institute Training | Certified by VLSI Guru Institute",
            "bullets": [
                "Completed a 2-month offline program on digital design flows and verification methodologies.",
                "Studied RTL design concepts, functional verification approaches, testbench development fundamentals and timing analysis principles.",
                "Earned certification on successful completion of all coursework and assessments.",
            ],
        },
        {
            "track": "it",
            "title": "Artificial Intelligence Intern — iStudio, Pune",
            "dates": "Apr 2026 – May 2026",
            "subtitle": "Selected via Internship Common Aptitude Test (iCAT)",
            "bullets": [
                "Developed a two-stage face recognition system in Python using PCA (Eigenfaces) and an MLP neural network classifier on the LFW dataset.",
                "Implemented imposter detection using distance-threshold logic (ACCEPTED / REJECTED output).",
                "Delivered the full pipeline from data acquisition to visualisation; earned a Training & Internship Certificate.",
            ],
        },
    ],
    "projects": [
        {
            "track": "it",
            "title": "Face Recognition System using PCA & Neural Networks",
            "dates": "Apr – May 2026",
            "subtitle": "Python · scikit-learn · OpenCV · NumPy · Matplotlib | iStudio AI Internship Final Project",
            "bullets": [
                "Built a PCA-based Eigenface pipeline reducing image vectors from 10,000 dimensions to k components (k = 2, 5, 10, 20) for efficient classification.",
                "Trained and tested an MLP classifier on the LFW dataset and visualised the Mean Face and Eigenfaces using Matplotlib.",
            ],
        },
        {
            "track": "core",
            "title": "Real-Time Digital Clock — Arduino UNO",
            "dates": "Aug – Sep 2025",
            "subtitle": "Embedded C · Arduino UNO · 7-Segment Display | Team Project (6 Members)",
            "bullets": [
                "Led a 6-member team to deliver a real-time digital clock in 4 weeks, managing tasks, hardware integration and documentation.",
                "Programmed timekeeping logic and display-multiplexing routines in Embedded C with hardware interrupt handling for accurate real-time operation.",
            ],
        },
    ],
    "certifications": [
        "VLSI Design & Verification — VLSI Guru Institute, Bengaluru (Jul 2025)",
        "AI Training & Internship Certificate — iStudio, Pune (May 2026)",
    ],
    "achievements": [
        "Qualified the competitive iCAT by iStudio, Pune, securing an internship from a national applicant pool.",
        "Scored 100% in Class X (State Board) and 90.3% in Class XII (MPC).",
    ],
}


def _slugify(text: str, max_len: int = 32) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "role").strip()).strip("_")
    return cleaned[:max_len].strip("_") or "role"


def _esc(text: str) -> str:
    return escape(str(text or ""))


def _extract_jd_keywords(jd_text: str) -> list[str]:
    lower = (jd_text or "").lower()
    return [kw for kw in TECH_KEYWORDS if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", lower)]


def _is_core_ece_role(job: dict) -> bool:
    track = (job.get("track") or "").lower()
    if "core" in track:
        return True
    if track == "it":
        return False
    text = f"{job.get('title', '')} {job.get('jd', '')}".lower()
    core_hits = sum(
        1 for k in ("vlsi", "rtl", "embedded", "firmware", "hardware", "fpga", "asic", "microcontroller", "ece")
        if k in text
    )
    it_hits = sum(
        1 for k in ("software", "python", "ai", "ml", "data", "web", "developer", "java", "qa")
        if k in text
    )
    return core_hits >= it_hits


def _compute_ats_report(resume_text: str, jd_text: str) -> dict:
    jd_kws = _extract_jd_keywords(jd_text)
    res_lower = resume_text.lower()
    matched = [kw for kw in jd_kws if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", res_lower)]
    missing = [kw for kw in jd_kws if kw not in matched]

    match_pct = int(round((len(matched) / len(jd_kws)) * 100)) if jd_kws else 82
    words = len(resume_text.split())
    length_bonus = 15 if 280 <= words <= 700 else 8
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
    is_core = _is_core_ece_role(job)

    if is_core:
        tagline = "VLSI Design & Verification  |  Embedded Systems & Firmware  |  B.Tech ECE (2027)"
        default_summary = (
            "Final-year B.Tech (ECE) student with hands-on training in VLSI Design & Verification (VLSI Guru Institute, Bengaluru) "
            "and Embedded Systems (Embedded C, Arduino UNO, hardware interrupts, UART/SPI/I2C). Backed by a strong foundation in "
            "Digital Electronics, Microprocessors & Microcontrollers, RTL design concepts, and Python/C programming. "
            "Seeking an entry-level role or internship in VLSI, embedded systems, or hardware engineering."
        )
        skill_order = ["Core Electronics & VLSI", "Embedded Systems", "Protocols", "Languages", "Software & Tools"]
    else:
        tagline = "Python & Software Development  |  AI/ML & Data Analytics  |  B.Tech ECE (2027)"
        default_summary = (
            "Final-year B.Tech (ECE) student with hands-on software and AI/ML experience in Python (NumPy, scikit-learn, OpenCV, Matplotlib), "
            "C, Java (Basic), Git, and Linux, including an Artificial Intelligence internship at iStudio, Pune. Backed by a strong foundation in "
            "Data Structures & Algorithms (C), Linear Algebra & Probability, and VLSI/embedded systems training. "
            "Seeking an entry-level role in software engineering, data analytics, or AI/ML."
        )
        skill_order = ["Languages", "Software & Tools", "Embedded Systems", "Core Electronics & VLSI", "Protocols"]

    skill_map = dict(MASTER_DEFAULTS["skill_categories"])
    ordered_skills = [(cat, skill_map[cat]) for cat in skill_order if cat in skill_map]

    target_track = "core" if is_core else "it"
    internships = sorted(MASTER_DEFAULTS["internships"], key=lambda x: 0 if x["track"] == target_track else 1)
    projects = sorted(MASTER_DEFAULTS["projects"], key=lambda x: 0 if x["track"] == target_track else 1)

    c = profile.get("contact") if isinstance(profile.get("contact"), dict) else {}
    phone = profile.get("phone") or c.get("phone") or MASTER_DEFAULTS["phone"]
    email = profile.get("email") or c.get("email") or MASTER_DEFAULTS["email"]
    location = profile.get("location") or c.get("location") or MASTER_DEFAULTS["location"]

    return {
        "name": profile.get("name") or MASTER_DEFAULTS["name"],
        "tagline": tagline,
        "contact": f"{phone}  |  {email}  |  {location}",
        "summary": (analysis or {}).get("tailored_summary") or default_summary,
        "education": MASTER_DEFAULTS["education"],
        "skill_categories": ordered_skills,
        "internships": internships,
        "projects": projects,
        "certifications": MASTER_DEFAULTS["certifications"],
        "achievements": MASTER_DEFAULTS["achievements"],
    }


def _pdf_lr_row(
    left_html: str,
    right_text: str,
    left_style: ParagraphStyle,
    right_style: ParagraphStyle,
    usable_width: float,
) -> Table:
    date_w = 1.45 * inch
    tbl = Table(
        [[Paragraph(left_html, left_style), Paragraph(_esc(right_text), right_style)]],
        colWidths=[usable_width - date_w, date_w],
        hAlign="LEFT",
    )
    tbl.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tbl


def _write_pdf(sections: dict, pdf_path: Path) -> None:
    margin_lr = 0.48 * inch
    margin_tb = 0.36 * inch
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=margin_lr,
        rightMargin=margin_lr,
        topMargin=margin_tb,
        bottomMargin=margin_tb,
    )
    usable_w = doc.width

    styles = getSampleStyleSheet()
    navy = colors.HexColor("#1e3a8a")
    dark = colors.HexColor("#0f172a")
    muted = colors.HexColor("#475569")
    rule_col = colors.HexColor("#1e3a8a")

    name_st = ParagraphStyle(
        "Name", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=16.5, leading=19.5, textColor=dark, alignment=TA_CENTER, spaceAfter=2,
    )
    tag_st = ParagraphStyle(
        "Tag", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9.0, leading=11.5, textColor=navy, alignment=TA_CENTER, spaceAfter=2,
    )
    contact_st = ParagraphStyle(
        "Contact", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.4, leading=10.5, textColor=muted, alignment=TA_CENTER, spaceAfter=5,
    )
    sec_st = ParagraphStyle(
        "Sec", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9.4, leading=11.5, textColor=navy, alignment=TA_LEFT, spaceBefore=6.5, spaceAfter=1.5,
    )
    title_st = ParagraphStyle(
        "ItemTitle", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.9, leading=11.0, textColor=dark, alignment=TA_LEFT,
    )
    date_st = ParagraphStyle(
        "Date", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=8.3, leading=11.0, textColor=muted, alignment=TA_RIGHT,
    )
    sub_st = ParagraphStyle(
        "Sub", parent=styles["Normal"], fontName="Helvetica-Oblique",
        fontSize=8.2, leading=10.2, textColor=muted, alignment=TA_LEFT, spaceAfter=1.5,
    )
    body_st = ParagraphStyle(
        "Body", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=11.2, textColor=dark, alignment=TA_JUSTIFY, spaceAfter=1.8,
    )
    skill_st = ParagraphStyle(
        "Skill", parent=body_st, alignment=TA_LEFT, spaceAfter=1.6,
    )
    bullet_st = ParagraphStyle(
        "Bullet", parent=body_st, leftIndent=12, bulletIndent=3, spaceAfter=1.6,
    )

    story = [
        Paragraph(_esc(sections["name"]), name_st),
        Paragraph(_esc(sections["tagline"]), tag_st),
        Paragraph(_esc(sections["contact"]), contact_st),
        HRFlowable(width="100%", thickness=1.1, color=rule_col, spaceBefore=0, spaceAfter=4),
    ]

    def add_section(heading: str) -> None:
        story.append(Paragraph(heading, sec_st))
        story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#94a3b8"), spaceBefore=0, spaceAfter=3))

    add_section("PROFESSIONAL SUMMARY")
    story.append(Paragraph(_esc(sections["summary"]), body_st))

    add_section("EDUCATION")
    for ed in sections["education"]:
        block = [
            _pdf_lr_row(f"<b>{_esc(ed['title'])}</b>", ed["dates"], title_st, date_st, usable_w),
            Paragraph(_esc(ed["subtitle"]), sub_st),
        ]
        if ed.get("extra"):
            block.append(Paragraph(_esc(ed["extra"]), body_st))
        story.append(KeepTogether(block))

    add_section("TECHNICAL SKILLS")
    for cat, vals in sections["skill_categories"]:
        story.append(Paragraph(f"<b>{_esc(cat)}:</b> {_esc(vals)}", skill_st))

    add_section("INTERNSHIPS &amp; TRAINING")
    for exp in sections["internships"]:
        block = [
            _pdf_lr_row(f"<b>{_esc(exp['title'])}</b>", exp["dates"], title_st, date_st, usable_w),
            Paragraph(_esc(exp["subtitle"]), sub_st),
        ]
        for b in exp["bullets"]:
            block.append(Paragraph(_esc(b), bullet_st, bulletText="•"))
        story.append(KeepTogether(block))

    add_section("PROJECTS")
    for proj in sections["projects"]:
        block = [
            _pdf_lr_row(f"<b>{_esc(proj['title'])}</b>", proj["dates"], title_st, date_st, usable_w),
            Paragraph(_esc(proj["subtitle"]), sub_st),
        ]
        for b in proj["bullets"]:
            block.append(Paragraph(_esc(b), bullet_st, bulletText="•"))
        story.append(KeepTogether(block))

    add_section("CERTIFICATIONS")
    for cert in sections["certifications"]:
        story.append(Paragraph(_esc(cert), bullet_st, bulletText="•"))

    add_section("ACHIEVEMENTS")
    for ach in sections["achievements"]:
        story.append(Paragraph(_esc(ach), bullet_st, bulletText="•"))

    doc.build(story)


def _add_docx_bottom_border(paragraph, color_hex: str = "94A3B8", sz: str = "6") -> None:
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), sz)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color_hex)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _write_docx(sections: dict, docx_path: Path) -> None:
    doc = Document()
    margin_lr = 0.48
    margin_tb = 0.36
    usable_in = 8.27 - (2 * margin_lr)  # Exact A4 printable width (7.31 in)

    for sec in doc.sections:
        sec.page_width = Inches(8.27)
        sec.page_height = Inches(11.69)
        sec.top_margin = Inches(margin_tb)
        sec.bottom_margin = Inches(margin_tb)
        sec.left_margin = Inches(margin_lr)
        sec.right_margin = Inches(margin_lr)

    navy = RGBColor(0x1E, 0x3A, 0x8A)
    dark = RGBColor(0x0F, 0x17, 0x2A)
    muted = RGBColor(0x47, 0x55, 0x69)

    def add_section_header(text: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6.5)
        p.paragraph_format.space_after = Pt(2.5)
        r = p.add_run(text)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(9.8)
        r.font.color.rgb = navy
        _add_docx_bottom_border(p, "94A3B8", "6")

    def add_lr_line(left: str, right: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2.5)
        p.paragraph_format.space_after = Pt(0.5)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(usable_in), WD_TAB_ALIGNMENT.RIGHT)
        r1 = p.add_run(left)
        r1.bold = True
        r1.font.name = "Calibri"
        r1.font.size = Pt(9.2)
        r1.font.color.rgb = dark
        r2 = p.add_run(f"\t{right}")
        r2.bold = True
        r2.font.name = "Calibri"
        r2.font.size = Pt(8.5)
        r2.font.color.rgb = muted

    def add_body(text: str, size: float = 8.8, italic: bool = False, color: RGBColor = dark, justify: bool = True) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1.5)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if justify else WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(text)
        r.italic = italic
        r.font.name = "Calibri"
        r.font.size = Pt(size)
        r.font.color.rgb = color

    def add_bullet(text: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.18)
        p.paragraph_format.first_line_indent = Inches(-0.14)
        p.paragraph_format.space_after = Pt(1.5)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r = p.add_run(f"•  {text}")
        r.font.name = "Calibri"
        r.font.size = Pt(8.7)
        r.font.color.rgb = dark

    # Centered Header
    p_name = doc.add_paragraph()
    p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_name.paragraph_format.space_after = Pt(1)
    r_name = p_name.add_run(sections["name"])
    r_name.bold = True
    r_name.font.name = "Calibri"
    r_name.font.size = Pt(17)
    r_name.font.color.rgb = dark

    p_tag = doc.add_paragraph()
    p_tag.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_tag.paragraph_format.space_after = Pt(1.5)
    r_tag = p_tag.add_run(sections["tagline"])
    r_tag.bold = True
    r_tag.font.name = "Calibri"
    r_tag.font.size = Pt(9.3)
    r_tag.font.color.rgb = navy

    p_con = doc.add_paragraph()
    p_con.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_con.paragraph_format.space_after = Pt(4)
    r_con = p_con.add_run(sections["contact"])
    r_con.font.name = "Calibri"
    r_con.font.size = Pt(8.6)
    r_con.font.color.rgb = muted
    _add_docx_bottom_border(p_con, "1E3A8A", "10")

    add_section_header("PROFESSIONAL SUMMARY")
    add_body(sections["summary"], size=8.8, justify=True)

    add_section_header("EDUCATION")
    for ed in sections["education"]:
        add_lr_line(ed["title"], ed["dates"])
        add_body(ed["subtitle"], size=8.4, italic=True, color=muted, justify=False)
        if ed.get("extra"):
            add_body(ed["extra"], size=8.6, justify=True)

    add_section_header("TECHNICAL SKILLS")
    for cat, vals in sections["skill_categories"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1.5)
        r_cat = p.add_run(f"{cat}: ")
        r_cat.bold = True
        r_cat.font.name = "Calibri"
        r_cat.font.size = Pt(8.7)
        r_cat.font.color.rgb = dark
        r_val = p.add_run(vals)
        r_val.font.name = "Calibri"
        r_val.font.size = Pt(8.7)
        r_val.font.color.rgb = dark

    add_section_header("INTERNSHIPS & TRAINING")
    for exp in sections["internships"]:
        add_lr_line(exp["title"], exp["dates"])
        add_body(exp["subtitle"], size=8.3, italic=True, color=muted, justify=False)
        for b in exp["bullets"]:
            add_bullet(b)

    add_section_header("PROJECTS")
    for proj in sections["projects"]:
        add_lr_line(proj["title"], proj["dates"])
        add_body(proj["subtitle"], size=8.3, italic=True, color=muted, justify=False)
        for b in proj["bullets"]:
            add_bullet(b)

    add_section_header("CERTIFICATIONS")
    for cert in sections["certifications"]:
        add_bullet(cert)

    add_section_header("ACHIEVEMENTS")
    for ach in sections["achievements"]:
        add_bullet(ach)

    doc.save(str(docx_path))


def create_tailored_resume_with_ats(profile: dict, analysis: dict | None, job: dict) -> tuple[str, dict]:
    """Generates both PDF (for applying) and DOCX (for editing) and returns (pdf_path, ats_report)."""
    sections = _build_tailored_sections(profile, analysis, job)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    comp_slug = _slugify(job.get("company", "Company"), max_len=24)
    role_slug = _slugify(job.get("title", "Role"), max_len=30)
    if comp_slug.lower() == role_slug.lower() or comp_slug.lower() in role_slug.lower():
        base_name = f"Sruthi_M_{role_slug}_{stamp}"
    else:
        base_name = f"Sruthi_M_{comp_slug}_{role_slug}_{stamp}"

    pdf_path = RESUMES_DIR / f"{base_name}.pdf"
    docx_path = RESUMES_DIR / f"{base_name}.docx"

    _write_pdf(sections, pdf_path)
    _write_docx(sections, docx_path)

    plain_text = " ".join(
        [
            sections["name"],
            sections["tagline"],
            sections["summary"],
            " ".join(f"{k} {v}" for k, v in sections["skill_categories"]),
            str(sections["internships"]),
            str(sections["projects"]),
            " ".join(sections["certifications"]),
            " ".join(sections["achievements"]),
        ]
    )
    ats_report = _compute_ats_report(plain_text, f"{job.get('title', '')}\n{job.get('jd', '')}")
    ats_report["pdf_path"] = str(pdf_path)
    ats_report["docx_path"] = str(docx_path)

    return str(pdf_path), ats_report