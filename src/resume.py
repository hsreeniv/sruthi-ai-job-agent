from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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

# Verified master data matching Sruthi's reference resume
MASTER_DEFAULTS = {
    "name": "SRUTHI M",
    "phone": "+91 9014771797",
    "email": "shrutimurugesh@gmail.com",
    "location": "Kuppam, Andhra Pradesh",
    "education": [
        {
            "title": "B.Tech — Electronics & Communication Engineering",
            "dates": "Sep 2023 – May 2027",
            "subtitle": "Aditya College of Engineering, Madanapalle | JNTU Anantapur  |  CGPA: 7.5/10",
            "extra": "Coursework: Digital Electronics, Microprocessors & Microcontrollers, Signals & Systems, Data Structures & Algorithms (C), Linear Algebra & Probability",
        },
        {
            "title": "Intermediate (Class XII) — MPC",
            "dates": "2021 – 2023",
            "subtitle": "Sri Chaitanya Junior College, Tirupathi  |  Score: 90.3%",
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


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "role").strip()).strip("_")
    return cleaned[:40] or "role"


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
    core_hits = sum(1 for k in ("vlsi", "rtl", "embedded", "firmware", "hardware", "fpga", "asic", "microcontroller", "ece") if k in text)
    it_hits = sum(1 for k in ("software", "python", "ai", "ml", "data", "web", "developer", "java", "qa") if k in text)
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

    # Prioritize track-matching internship and project first
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
        "contact": f"{phone}  ·  {email}  ·  {location}",
        "summary": (analysis or {}).get("tailored_summary") or default_summary,
        "education": MASTER_DEFAULTS["education"],
        "skill_categories": ordered_skills,
        "internships": internships,
        "projects": projects,
        "certifications": MASTER_DEFAULTS["certifications"],
        "achievements": MASTER_DEFAULTS["achievements"],
    }


def _pdf_lr_row(left_html: str, right_text: str, left_style: ParagraphStyle, right_style: ParagraphStyle) -> Table:
    tbl = Table(
        [[Paragraph(left_html, left_style), Paragraph(_esc(right_text), right_style)]],
        colWidths=[5.65 * inch, 1.65 * inch],
    )
    tbl.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tbl


def _write_pdf(sections: dict, pdf_path: Path) -> None:
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=0.48 * inch,
        rightMargin=0.48 * inch,
        topMargin=0.38 * inch,
        bottomMargin=0.38 * inch,
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#1e3a8a")
    dark = colors.HexColor("#0f172a")
    muted = colors.HexColor("#475569")

    name_st = ParagraphStyle("Name", parent=styles["Heading1"], fontSize=16.5, leading=19, textColor=dark, spaceAfter=1)
    tag_st = ParagraphStyle("Tag", parent=styles["Normal"], fontSize=9.0, leading=11.5, textColor=navy, spaceAfter=1)
    contact_st = ParagraphStyle("Contact", parent=styles["Normal"], fontSize=8.3, leading=10.5, textColor=muted, spaceAfter=4)
    sec_st = ParagraphStyle("Sec", parent=styles["Heading2"], fontSize=9.6, leading=11.5, textColor=navy, spaceBefore=6, spaceAfter=2)
    title_st = ParagraphStyle("ItemTitle", parent=styles["Normal"], fontSize=9.0, leading=11.2, textColor=dark)
    date_st = ParagraphStyle("Date", parent=styles["Normal"], fontSize=8.3, leading=11.2, textColor=muted, alignment=2)
    sub_st = ParagraphStyle("Sub", parent=styles["Normal"], fontSize=8.3, leading=10.5, textColor=muted, spaceAfter=1.5)
    body_st = ParagraphStyle("Body", parent=styles["Normal"], fontSize=8.6, leading=11.2, textColor=dark, spaceAfter=1.8)
    bullet_st = ParagraphStyle("Bullet", parent=body_st, leftIndent=10, firstLineIndent=-8, spaceAfter=1.5)

    def add_section(heading: str) -> None:
        story.append(Paragraph(heading, sec_st))
        story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#94a3b8"), spaceAfter=3))

    story = [
        Paragraph(f"<b>{_esc(sections['name'])}</b>", name_st),
        Paragraph(f"<b>{_esc(sections['tagline'])}</b>", tag_st),
        Paragraph(_esc(sections["contact"]), contact_st),
    ]

    add_section("PROFESSIONAL SUMMARY")
    story.append(Paragraph(_esc(sections["summary"]), body_st))

    add_section("EDUCATION")
    for ed in sections["education"]:
        story.append(_pdf_lr_row(f"<b>{_esc(ed['title'])}</b>", ed["dates"], title_st, date_st))
        story.append(Paragraph(_esc(ed["subtitle"]), sub_st))
        if ed.get("extra"):
            story.append(Paragraph(_esc(ed["extra"]), body_st))

    add_section("TECHNICAL SKILLS")
    for cat, vals in sections["skill_categories"]:
        story.append(Paragraph(f"<b>{_esc(cat)}:</b> {_esc(vals)}", body_st))

    add_section("INTERNSHIPS &amp; TRAINING")
    for exp in sections["internships"]:
        story.append(_pdf_lr_row(f"<b>{_esc(exp['title'])}</b>", exp["dates"], title_st, date_st))
        story.append(Paragraph(f"<i>{_esc(exp['subtitle'])}</i>", sub_st))
        for b in exp["bullets"]:
            story.append(Paragraph(f"•  {_esc(b)}", bullet_st))

    add_section("PROJECTS")
    for proj in sections["projects"]:
        story.append(_pdf_lr_row(f"<b>{_esc(proj['title'])}</b>", proj["dates"], title_st, date_st))
        story.append(Paragraph(f"<i>{_esc(proj['subtitle'])}</i>", sub_st))
        for b in proj["bullets"]:
            story.append(Paragraph(f"•  {_esc(b)}", bullet_st))

    add_section("CERTIFICATIONS")
    for cert in sections["certifications"]:
        story.append(Paragraph(f"•  {_esc(cert)}", bullet_st))

    add_section("ACHIEVEMENTS")
    for ach in sections["achievements"]:
        story.append(Paragraph(f"•  {_esc(ach)}", bullet_st))

    doc.build(story)


def _add_docx_bottom_border(paragraph) -> None:
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "94A3B8")
    pBdr.append(bottom)
    pPr.append(pBdr)


def _write_docx(sections: dict, docx_path: Path) -> None:
    doc = Document()
    for sec in doc.sections:
        sec.top_margin = Inches(0.42)
        sec.bottom_margin = Inches(0.42)
        sec.left_margin = Inches(0.52)
        sec.right_margin = Inches(0.52)

    navy = RGBColor(0x1E, 0x3A, 0x8A)
    dark = RGBColor(0x0F, 0x17, 0x2A)
    muted = RGBColor(0x47, 0x55, 0x69)

    def add_section_header(text: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2.5)
        r = p.add_run(text)
        r.bold = True
        r.font.size = Pt(9.8)
        r.font.color.rgb = navy
        _add_docx_bottom_border(p)

    def add_lr_line(left: str, right: str) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(0.5)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(7.2), WD_TAB_ALIGNMENT.RIGHT)
        r1 = p.add_run(left)
        r1.bold = True
        r1.font.size = Pt(9.2)
        r1.font.color.rgb = dark
        r2 = p.add_run(f"\t{right}")
        r2.font.size = Pt(8.5)
        r2.font.color.rgb = muted

    def add_line(text: str, size: float = 8.8, italic: bool = False, color: RGBColor = dark) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1.5)
        r = p.add_run(text)
        r.italic = italic
        r.font.size = Pt(size)
        r.font.color.rgb = color

    # Header
    p_name = doc.add_paragraph()
    p_name.paragraph_format.space_after = Pt(1)
    r_name = p_name.add_run(sections["name"])
    r_name.bold = True
    r_name.font.size = Pt(16.5)
    r_name.font.color.rgb = dark

    p_tag = doc.add_paragraph()
    p_tag.paragraph_format.space_after = Pt(1)
    r_tag = p_tag.add_run(sections["tagline"])
    r_tag.bold = True
    r_tag.font.size = Pt(9.2)
    r_tag.font.color.rgb = navy

    add_line(sections["contact"], size=8.5, color=muted)

    add_section_header("PROFESSIONAL SUMMARY")
    add_line(sections["summary"], size=8.8)

    add_section_header("EDUCATION")
    for ed in sections["education"]:
        add_lr_line(ed["title"], ed["dates"])
        add_line(ed["subtitle"], size=8.5, color=muted)
        if ed.get("extra"):
            add_line(ed["extra"], size=8.5)

    add_section_header("TECHNICAL SKILLS")
    for cat, vals in sections["skill_categories"]:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(1.5)
        r_cat = p.add_run(f"{cat}: ")
        r_cat.bold = True
        r_cat.font.size = Pt(8.8)
        r_val = p.add_run(vals)
        r_val.font.size = Pt(8.8)

    add_section_header("INTERNSHIPS & TRAINING")
    for exp in sections["internships"]:
        add_lr_line(exp["title"], exp["dates"])
        add_line(exp["subtitle"], size=8.4, italic=True, color=muted)
        for b in exp["bullets"]:
            add_line(f"•  {b}", size=8.7)

    add_section_header("PROJECTS")
    for proj in sections["projects"]:
        add_lr_line(proj["title"], proj["dates"])
        add_line(proj["subtitle"], size=8.4, italic=True, color=muted)
        for b in proj["bullets"]:
            add_line(f"•  {b}", size=8.7)

    add_section_header("CERTIFICATIONS")
    for cert in sections["certifications"]:
        add_line(f"•  {cert}", size=8.7)

    add_section_header("ACHIEVEMENTS")
    for ach in sections["achievements"]:
        add_line(f"•  {ach}", size=8.7)

    doc.save(str(docx_path))


def create_tailored_resume_with_ats(profile: dict, analysis: dict | None, job: dict) -> tuple[str, dict]:
    """Generates both PDF (for applying) and DOCX (for editing) and returns (pdf_path, ats_report)."""
    sections = _build_tailored_sections(profile, analysis, job)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"Sruthi_M_{_slugify(job.get('company', 'Company'))}_{_slugify(job.get('title', 'Role'))}_{stamp}"

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