from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.db import init_db
from src.discovery import discover_and_store
from src.notifier import send_daily_digest
from src.profile import load_profile

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "daily_discovery.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
LOG = logging.getLogger("daily_runner")


def main() -> None:
    load_dotenv(".env")
    init_db()
    profile = load_profile()
    target = int(profile.get("daily_discovery_target", 100))

    LOG.info("=== Starting daily discovery run (target=%s) ===", target)
    result = discover_and_store(profile, target=target, include_job_boards=True)

    LOG.info("Summary:\n%s", result["summary"])
    top_likely = [
        j for j in result.get("jobs", []) if j.get("eligibility_status") == "Likely eligible"
    ][:10]

    if top_likely:
        LOG.info("Top Likely Eligible roles found today (%s):", len(top_likely))
        for j in top_likely:
            LOG.info(
                "  [%s] %s — %s (%s) | %s",
                j.get("match_score"),
                j.get("company"),
                j.get("title"),
                j.get("location"),
                j.get("source"),
            )
    else:
        LOG.info("No new 'Likely eligible' roles in this run.")

    if result.get("errors"):
        LOG.warning("Errors encountered (%s): %s", len(result["errors"]), result["errors"][:5])

    send_daily_digest(result["summary"], result.get("jobs", []))
    LOG.info("=== Finished daily discovery at %s ===", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main()