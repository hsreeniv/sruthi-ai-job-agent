from __future__ import annotations

import re
from typing import Any

ELIGIBLE = "Likely eligible"
REVIEW = "Review required"
INELIGIBLE = "Ineligible based on explicit requirement"

INDIA_LOCATIONS = (
    "india",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "chennai",
    "noida",
    "mumbai",
    "gurugram",
    "gurgaon",
    "delhi",
    "kolkata",
    "ahmedabad",
    "kochi",
    "coimbatore",
    "mysuru",
    "mysore",
    "karnataka",
    "telangana",
    "tamil nadu",
    "maharashtra",
    "andhra pradesh",
    "serilingampalli",
    "secunderabad",
    "whitefield",
    "electronic city",
    "navi mumbai",
    "thane",
    "thiruvananthapuram",
    "trivandrum",
    "visakhapatnam",
    "vizag",
    "indore",
    "chandigarh",
    "jaipur",
)

NON_INDIA_COUNTRY_TAGS = (
    ", sk", ", de", ", pl", ", cz", ", hu", ", ro", ", bg", ", at", ", ch",
    ", fr", ", es", ", it", ", nl", ", be", ", se", ", uk", ", gb", ", ie",
    ", us", ", ca", ", mx", ", br", ", sg", ", jp", ", cn", ", kr", ", au",
    "slovakia", "germany", "poland", "czech", "united states", "usa", "united kingdom",
    "singapore", "canada", "australia", "europe", "emea", "latam",
)

EXCLUDED_TITLE_KEYWORDS = (
    "content creator",
    "associate - content",
    "copywriter",
    "fraud analyst",
    "risk analyst",
    "financial analyst",
    "finance ",
    "accountant",
    "recruiter",
    "human resources",
    "hr ",
    "sales",
    "business development",
    "marketing",
    "customer support",
    "servisnÃ½ technik",
    "servisna technicka",
    "technician",
    "sap ",
    "sap_",
    "consultant",
    "legal",
    "counsel",
)

SENIOR_TITLE_KEYWORDS = (
    "senior",
    "sr.",
    "sr ",
    "staff ",
    "principal",
    "lead ",
    "tech lead",
    "team lead",
    "manager",
    "director",
    "vp ",
    "head of",
    "architect",
    "expert",
    "iii",
    "iv",
)

ENTRY_KEYWORDS = (
    "intern",
    "internship",
    "trainee",
    "graduate",
    "grad ",
    "fresher",
    "entry level",
    "entry-level",
    "junior",
    "jr.",
    "apprentice",
    "campus",
    "2027",
    "2026",
    "associate engineer",
    "software engineer i",
    "engineer 1",
    "engineer i",
)

IT_KEYWORDS = (
    "software",
    "developer",
    "python",
    "java",
    "backend",
    "frontend",
    "full stack",
    "fullstack",
    "data",
    "ai",
    "ml",
    "machine learning",
    "cloud",
    "devops",
    "qa",
    "sdet",
    "test",
    "automation",
    "web",
    "android",
    "ios",
    "security",
    "cyber",
)

CORE_ECE_KEYWORDS = (
    "ece",
    "electronics",
    "vlsi",
    "rtl",
    "asic",
    "fpga",
    "verification",
    "embedded",
    "firmware",
    "microcontroller",
    "hardware",
    "semiconductor",
    "dsp",
    "signal",
    "rf",
    "telecom",
    "iot",
    "pcb",
)


def _is_india_location(location: str) -> bool:
    loc = (location or "").strip().lower()
    if not loc:
        return False
    if any(bad in loc for bad in NON_INDIA_COUNTRY_TAGS):
        return False
    return any(good in loc for good in INDIA_LOCATIONS)


def _detect_track(title_low: str, jd_low: str) -> str:
    combined = f"{title_low} {jd_low}"
    core_hits = sum(1 for k in CORE_ECE_KEYWORDS if k in combined)
    it_hits = sum(1 for k in IT_KEYWORDS if k in combined)
    if core_hits > it_hits and core_hits > 0:
        return "Core Engineering"
    if it_hits > 0:
        return "IT"
    return "Other"


def evaluate_job(job: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Evaluate 2027 B.Tech ECE eligibility, India location, engineering track, and match score."""
    title = (job.get("title") or "").strip()
    location = (job.get("location") or "").strip()
    jd = (job.get("jd") or "").strip()

    title_low = title.lower()
    jd_low = jd.lower()
    combined = f"{title_low}\n{jd_low}"
    reasons: list[str] = []

    # 1. Location check (India / Bengaluru priority)
    if not _is_india_location(location):
        return {
            "eligible": False,
            "bengaluru_priority": False,
            "eligibility_status": INELIGIBLE,
            "track": "Other",
            "match_score": 0,
            "eligibility_reasons": [f"Location '{location}' is outside India."],
        }

    is_bengaluru = "bengaluru" in location.lower() or "bangalore" in location.lower()
    if is_bengaluru:
        reasons.append("Priority location matched: Bengaluru.")
    else:
        reasons.append(f"Eligible India location matched: {location}.")

    # 2. Exclude non-engineering / non-technical roles
    for bad_title in EXCLUDED_TITLE_KEYWORDS:
        if bad_title in title_low:
            return {
                "eligible": False,
            "bengaluru_priority": False,
                "eligibility_status": INELIGIBLE,
                "track": "Other",
                "match_score": 0,
                "eligibility_reasons": [f"Excluded non-engineering/non-target title keyword: '{bad_title.strip()}'."],
            }

    # 3. Exclude senior-level titles
    for sen in SENIOR_TITLE_KEYWORDS:
        if sen in title_low:
            return {
                "eligible": False,
            "bengaluru_priority": False,
                "eligibility_status": INELIGIBLE,
                "track": _detect_track(title_low, jd_low),
                "match_score": 0,
                "eligibility_reasons": [f"Senior-level role ('{sen.strip()}') excluded for 2027 fresher profile."],
            }

    # 4. Check explicit high experience requirements in JD (e.g., 3+ years, 5+ years)
    exp_matches = re.findall(r"\b([3-9]|1\d)\s*\+?\s*(?:years|yrs)\b", jd_low)
    if exp_matches and not any(k in title_low for k in ("intern", "trainee", "graduate", "fresher")):
        return {
            "eligible": False,
            "bengaluru_priority": False,
            "eligibility_status": INELIGIBLE,
            "track": _detect_track(title_low, jd_low),
            "match_score": 0,
            "eligibility_reasons": [f"Requires {exp_matches[0]}+ years of experience (not fresher/2027 eligible)."],
        }

    # 4b. Reject explicit non-2027 graduation/batch requirements
    passout_year = str(profile.get("passout_year", 2027))
    mentioned_years = set(re.findall(r"\b(202[2-8])\b", combined))
    if mentioned_years and passout_year not in mentioned_years:
        return {
            "eligible": False,
            "bengaluru_priority": False,
            "eligibility_status": INELIGIBLE,
            "track": _detect_track(title_low, jd_low),
            "match_score": 0,
            "eligibility_reasons": [f"Explicitly targets {', '.join(sorted(mentioned_years))} batch, excluding {passout_year}."],
        }

    # 5. Track & profile skill overlap
    track = _detect_track(title_low, jd_low)
    if track == "Other":
        return {
            "eligible": False,
            "bengaluru_priority": False,
            "eligibility_status": INELIGIBLE,
            "track": "Other",
            "match_score": 0,
            "eligibility_reasons": ["Role does not match IT/Software or Core ECE engineering tracks."],
        }

    profile_skills = [str(s).lower() for s in profile.get("skills", [])]
    matched_skills = [s for s in profile_skills if re.search(rf"(?<![a-z0-9]){re.escape(s)}(?![a-z0-9])", combined)]

    has_entry_signal = any(k in title_low for k in ENTRY_KEYWORDS) or any(
        k in jd_low for k in ("2027", "internship", "fresher", "0-1 year", "0-2 years", "b.tech", "b.e")
    )

    score = 35
    if is_bengaluru:
        score += 15
    if has_entry_signal:
        score += 25
        reasons.append("Entry-level / internship / 2027 graduate signal detected.")
    else:
        reasons.append("No explicit fresher/intern tag in title; flagged for quick manual check.")

    score += min(25, len(matched_skills) * 5)
    if matched_skills:
        reasons.append(f"Matched verified skills ({len(matched_skills)}): {', '.join(matched_skills[:6])}.")

    score = min(100, score)
    has_2027_or_intern = ("2027" in combined) or ("intern" in title_low) or ("internship" in combined)
    eligibility_status = ELIGIBLE if (has_2027_or_intern and score >= 60) else REVIEW

    return {
        "eligible": True,
        "bengaluru_priority": is_bengaluru,
        "eligibility_status": eligibility_status,
        "track": track,
        "match_score": score,
        "eligibility_reasons": reasons,
    }


def sort_jobs_bengaluru_first(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort jobs with Bengaluru priority, then Likely eligible, then highest match score."""
    def _key(j: dict[str, Any]) -> tuple[int, int, int]:
        loc = (j.get("location") or "").lower()
        is_blr = 1 if (j.get("bengaluru_priority") or "bengaluru" in loc or "bangalore" in loc) else 0
        is_likely = 1 if j.get("eligibility_status") == ELIGIBLE else 0
        score = int(j.get("match_score") or 0)
        return (is_likely, is_blr, score)

    return sorted(jobs, key=_key, reverse=True)


