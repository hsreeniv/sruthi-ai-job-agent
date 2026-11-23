from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

LOG = logging.getLogger(__name__)


def send_daily_digest(summary: str, jobs: list[dict[str, Any]], max_items: int = 15) -> bool:
    """Send an HTML morning digest of top Likely eligible jobs via Gmail SMTP."""
    sender = os.getenv("SMTP_EMAIL", "").strip()
    app_password = os.getenv("SMTP_APP_PASSWORD", "").strip()
    recipient = os.getenv("DIGEST_TO_EMAIL", sender).strip()

    if not sender or not app_password or not recipient:
        LOG.info("Email digest skipped (SMTP_EMAIL / SMTP_APP_PASSWORD not configured in .env).")
        return False

    likely_jobs = [j for j in jobs if j.get("eligibility_status") == "Likely eligible"][:max_items]
    today_str = datetime.now().strftime("%d %b %Y")
    subject = f"Sruthi AI Job Agent — {len(likely_jobs)} Likely Eligible Roles ({today_str})"

    rows_html = ""
    for j in likely_jobs:
        url = j.get("url") or "#"
        rows_html += (
            f"<tr>"
            f"<td style='padding:6px;border:1px solid #ddd;'><b>{j.get('match_score', 0)}</b></td>"
            f"<td style='padding:6px;border:1px solid #ddd;'>{j.get('company', '')}</td>"
            f"<td style='padding:6px;border:1px solid #ddd;'><a href='{url}'>{j.get('title', '')}</a></td>"
            f"<td style='padding:6px;border:1px solid #ddd;'>{j.get('location', '')}</td>"
            f"<td style='padding:6px;border:1px solid #ddd;'>{j.get('source', '')}</td>"
            f"</tr>"
        )

    if not rows_html:
        rows_html = "<tr><td colspan='5' style='padding:8px;'>No new Likely eligible roles in this run.</td></tr>"

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #222;">
        <h2>Daily 24h Job Digest — {today_str}</h2>
        <pre style="background:#f6f8fa;padding:10px;border-radius:4px;">{summary}</pre>
        <table style="border-collapse:collapse;width:100%;font-size:13px;">
          <thead>
            <tr style="background:#f0f2f6;text-align:left;">
              <th style="padding:6px;border:1px solid #ddd;">Score</th>
              <th style="padding:6px;border:1px solid #ddd;">Company</th>
              <th style="padding:6px;border:1px solid #ddd;">Role</th>
              <th style="padding:6px;border:1px solid #ddd;">Location</th>
              <th style="padding:6px;border:1px solid #ddd;">Source</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
        <p style="margin-top:14px;font-size:12px;color:#555;">
          Open Streamlit (<code>python -m streamlit run app.py</code>) to tailor resumes, check ATS scores, and approve applications.
        </p>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(sender, app_password)
            server.sendmail(sender, [recipient], msg.as_string())
        LOG.info("Daily email digest sent to %s (%s roles).", recipient, len(likely_jobs))
        return True
    except Exception as exc:
        LOG.warning("Failed to send daily email digest: %s", exc)
        return False