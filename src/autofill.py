from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)


def _parse_contact_line(contact_line: str) -> dict[str, str]:
    """Extract verified email, phone, LinkedIn URL, and city from profile.contact_line."""
    email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", contact_line or "")
    phone_match = re.search(r"(?:\+91[\s-]?)?[6-9]\d{9}", contact_line or "")
    linkedin_match = re.search(r"https?://(?:www\.)?linkedin\.com/in/[^\s|·]+", contact_line or "")

    city = ""
    parts = [p.strip() for p in re.split(r"[|·]", contact_line or "") if p.strip()]
    for part in parts:
        if "@" not in part and not re.search(r"\d{7,}", part) and "linkedin.com" not in part.lower():
            city = part if "india" in part.lower() else f"{part}, India"
            break

    return {
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
        "linkedin": linkedin_match.group(0) if linkedin_match else "",
        "city": city,
    }


def _try_fill(page: Any, selectors: list[str], value: str) -> bool:
    if not value:
        return False
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.fill(value)
                return True
        except Exception:
            continue
    return False


def _try_fill_location_combobox(page: Any, city_query: str) -> bool:
    """Handle searchable Location (City) autocomplete inputs on ATS forms (skip LinkedIn search bars)."""
    if not city_query or "linkedin.com" in (page.url or "").lower():
        return False
    selectors = [
        "form input[id*='location' i]:not([type='search'])",
        "form input[name*='location' i]:not([type='search'])",
        "form input[aria-label*='Location (City)' i]",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click()
                loc.fill(city_query)
                page.wait_for_timeout(1200)
                short_city = city_query.split(",")[0].strip()
                option = page.locator(
                    f"[role='option']:has-text('{short_city}'), li:has-text('{short_city}'), div[class*='option']:has-text('{short_city}')"
                ).first
                if option.count() > 0 and option.is_visible():
                    option.click()
                    return True
        except Exception:
            continue
    return False


def _try_upload_resume(page: Any, resume_path: str | Path) -> bool:
    path = Path(resume_path)
    if not path.exists():
        return False
    for sel in [
        "input[type='file'][name*='resume' i]",
        "input[type='file'][id*='resume' i]",
        "input[type='file']",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.set_input_files(str(path.resolve()))
                return True
        except Exception:
            continue
    return False


def launch_prefill_browser(
    job_url: str,
    profile: dict[str, Any],
    resume_path: str | Path,
) -> dict[str, Any]:
    """Open the application page in a visible browser, prefill verified fields, and pause.

    SAFETY RULE: Never clicks any Submit / Apply button. Sruthi must review and submit manually.
    """
    if not job_url:
        raise ValueError("Job URL is empty. Add a valid URL before launching autofill.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: python -m pip install playwright && python -m playwright install chromium"
        ) from exc

    full_name = (profile.get("name") or "").strip()
    parts = full_name.split()
    first_name = parts[0] if parts else ""
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    contact = _parse_contact_line(profile.get("contact_line", ""))

    filled_fields: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)

        # Name fields
        if _try_fill(page, ["input[name='first_name']", "input[id*='first_name' i]", "input[placeholder*='First Name' i]"], first_name):
            filled_fields.append("first_name")
        if _try_fill(page, ["input[name='last_name']", "input[id*='last_name' i]", "input[placeholder*='Last Name' i]"], last_name):
            filled_fields.append("last_name")
        if "first_name" not in filled_fields:
            if _try_fill(page, ["input[name='name']", "input[placeholder*='Full Name' i]"], full_name):
                filled_fields.append("full_name")

        # Contact fields
        if _try_fill(page, ["input[type='email']", "input[name*='email' i]", "input[id*='email' i]"], contact["email"]):
            filled_fields.append("email")
        if _try_fill(page, ["input[type='tel']", "input[name*='phone' i]", "input[id*='phone' i]"], contact["phone"]):
            filled_fields.append("phone")
        if _try_fill(page, ["input[name*='linkedin' i]", "input[placeholder*='LinkedIn' i]"], contact["linkedin"]):
            filled_fields.append("linkedin")

        # Location (City) autocomplete (skipped on LinkedIn search bars)
        if _try_fill_location_combobox(page, contact["city"]):
            filled_fields.append("location_city")

        # Resume upload
        if _try_upload_resume(page, resume_path):
            filled_fields.append("resume")

        LOG.info("Prefilled fields %s. Waiting for manual review & close.", filled_fields)

        # Keep browser open until Sruthi reviews, submits manually, and closes the window
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        browser.close()

    return {
        "url": job_url,
        "filled_fields": filled_fields,
        "submitted_automatically": False,
    }