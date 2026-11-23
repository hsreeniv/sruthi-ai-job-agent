from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from docx import Document

# Curated technical keyword vocabulary across IT/Software/AI-ML and Core ECE/VLSI/Embedded
TECH_KEYWORDS = [
    # Languages
    "python", "c++", "c#", "java", "javascript", "typescript", "sql", "verilog",
    "systemverilog", "vhdl", "embedded c", "bash", "shell", "tcl", "perl", "matlab",
    # AI / ML / Data
    "machine learning", "deep learning", "data analysis", "data analytics", "data science",
    "numpy", "pandas", "scikit-learn", "opencv", "matplotlib", "tensorflow", "pytorch",
    "nlp", "computer vision", "neural network", "pca", "jupyter", "power bi", "tableau", "excel",
    # Software / QA / DevOps
    "git", "github", "linux", "docker", "kubernetes", "aws", "azure", "gcp", "rest api",
    "api", "fastapi", "flask", "django", "react", "node.js", "html", "css", "mongodb",
    "postgresql", "mysql", "sqlite", "ci/cd", "jenkins", "selenium", "playwright",
    "pytest", "automation", "testing", "qa", "agile", "scrum", "dsa", "data structures",
    "algorithms", "oop", "object oriented", "operating systems", "computer networks",
    # Core ECE / VLSI / Embedded
    "vlsi", "rtl", "asic", "fpga", "soc", "digital electronics", "digital logic",
    "fsm", "functional verification", "uvm", "testbench", "timing analysis", "sta",
    "synthesis", "modelsim", "vivado", "cadence", "synopsys", "semiconductor",
    "embedded", "embedded systems", "firmware", "microcontroller", "microprocessor",
    "arduino", "stm32", "arm", "rtos", "interrupt", "uart", "spi", "i2c", "can",
    "pcb", "oscilloscope", "signal processing", "dsp", "rf", "telecom", "iot",
]

REQUIRED_SECTIONS = [
    "PROFESSIONAL SUMMARY",
    "EDUCATION",
    "TECHNICAL SKILLS",
    "INTERNSHIPS & TRAINING",
    "PROJECTS",
]


def _word_boundary_match(term: str, text_lower: str) -> bool:
    t = term.lower()
    escaped = re.escape(t)
    # Allow optional plural 's' for multi-letter alphabetic terms (e.g., fsm -> FSMs)
    plural = "s?" if len(t) > 1 and t[-1].isalpha() and not t.endswith("s") else ""
    pattern = rf"(?<![a-z0-9+#]){escaped}{plural}(?![a-z0-9+#])"
    return re.search(pattern, text_lower) is not None


def extract_jd_keywords(jd_text: str, title: str = "", analysis: dict[str, Any] | None = None) -> list[str]:
    """Extract normalized technical keywords from the job title, JD, and optional Gemini analysis."""
    combined = f"{title}\n{jd_text}".lower()
    found: list[str] = []

    # Check single-letter 'C' carefully so it doesn't match random words
    if re.search(r"(?<![a-z0-9+#])c(?![a-z0-9+#])", combined) and any(
        hint in combined for hint in ["c/c++", "c,", "c ", "embedded c", "programming", "language"]
    ):
        found.append("c")

    for kw in TECH_KEYWORDS:
        if _word_boundary_match(kw, combined):
            found.append(kw)

    # Merge any skills Gemini explicitly extracted
    if analysis:
        for key in ("matched_skills", "missing_skills"):
            for item in analysis.get(key) or []:
                cleaned = str(item).strip().lower()
                if cleaned and cleaned not in found:
                    found.append(cleaned)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for k in found:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique


def read_docx_text(docx_path: str | Path) -> tuple[str, int, int]:
    """Return (full_text, table_count, image_count) from a .docx file."""
    doc = Document(str(docx_path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text.strip())
    image_count = len(doc.inline_shapes)
    return "\n".join(parts), len(doc.tables), image_count


def score_resume_against_jd(
    docx_path: str | Path,
    job: dict[str, Any],
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate an explainable 0-100 ATS score for a generated .docx resume against a job."""
    resume_text, table_count, image_count = read_docx_text(docx_path)
    resume_lower = resume_text.lower()
    resume_upper = resume_text.upper()
    word_count = len(re.findall(r"\b\w+\b", resume_text))

    jd_keywords = extract_jd_keywords(job.get("jd", ""), job.get("title", ""), analysis)
    matched: list[str] = []
    missing: list[str] = []

    for kw in jd_keywords:
        if _word_boundary_match(kw, resume_lower):
            matched.append(kw)
        else:
            missing.append(kw)

    # 1. Keyword Match Score (60 pts)
    if jd_keywords:
        keyword_ratio = len(matched) / len(jd_keywords)
        keyword_score = round(keyword_ratio * 60)
    else:
        keyword_ratio = 1.0
        keyword_score = 45  # Neutral baseline when JD has minimal technical text

    # 2. Section Completeness Score (20 pts)
    present_sections = [s for s in REQUIRED_SECTIONS if s in resume_upper]
    missing_sections = [s for s in REQUIRED_SECTIONS if s not in resume_upper]
    section_score = round((len(present_sections) / len(REQUIRED_SECTIONS)) * 20)

    # 3. ATS Formatting & Readability Score (20 pts)
    format_checks: list[str] = []
    format_score = 0

    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", resume_text))
    has_phone = bool(re.search(r"(?:\+91[\s-]?)?[6-9]\d{9}", resume_text))
    if has_email and has_phone:
        format_score += 5
        format_checks.append("PASS: Valid email and phone number detected.")
    else:
        format_checks.append("WARN: Missing email or phone number in resume header.")

    if table_count == 0 and image_count == 0:
        format_score += 5
        format_checks.append("PASS: Single-column layout with no tables or images (ATS-safe).")
    else:
        format_checks.append(f"WARN: Detected {table_count} tables and {image_count} images; may hinder ATS parsing.")

    if 300 <= word_count <= 750:
        format_score += 5
        format_checks.append(f"PASS: Concise 1-page length ({word_count} words).")
    else:
        format_score += 2
        format_checks.append(f"WARN: Word count is {word_count} (ideal 1-page fresher target: 300-750 words).")

    if "2027" in resume_text and "b.tech" in resume_lower:
        format_score += 5
        format_checks.append("PASS: Degree (B.Tech) and graduation year (2027) clearly stated.")
    else:
        format_checks.append("WARN: Ensure B.Tech and graduation year (2027) are explicitly listed.")

    total_score = max(0, min(100, keyword_score + section_score + format_score))
    if total_score >= 80:
        grade = "Strong ATS Match"
    elif total_score >= 60:
        grade = "Moderate ATS Match"
    else:
        grade = "Low ATS Match (Skill Gap)"

    recommendations: list[str] = []
    if missing:
        top_missing = ", ".join(missing[:8])
        recommendations.append(
            f"JD keywords absent from verified profile (do NOT fabricate; learn or verify if applicable): {top_missing}."
        )
    if missing_sections:
        recommendations.append(f"Add missing standard sections: {', '.join(missing_sections)}.")

    return {
        "ats_score": total_score,
        "grade": grade,
        "breakdown": {
            "keyword_score": keyword_score,
            "section_score": section_score,
            "format_score": format_score,
        },
        "jd_keyword_count": len(jd_keywords),
        "matched_keywords": matched,
        "missing_keywords": missing,
        "keyword_match_pct": round(keyword_ratio * 100, 1),
        "word_count": word_count,
        "format_checks": format_checks,
        "recommendations": recommendations,
    }