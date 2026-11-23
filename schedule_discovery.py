"""Runs daily discovery at 07:00 Asia/Kolkata. Keep running or use Windows Task Scheduler."""
import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from src.db import init_db
from src.discovery import discover_and_store
from src.profile import load_profile

load_dotenv()
init_db()
logging.basicConfig(
    filename="data/discovery.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def job() -> None:
    profile = load_profile()
    target = int(profile.get("daily_discovery_target", 100))
    result = discover_and_store(profile, target)
    logging.info("Daily 7:00 AM IST discovery completed:\n%s", result["summary"])
    for err in result["errors"]:
        logging.warning("Discovery source error: %s", err)


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        job,
        "cron",
        hour=7,
        minute=0,
        id="daily_job_discovery",
        max_instances=1,
        coalesce=True,
    )
    logging.info("Scheduler started; daily discovery scheduled for 07:00 Asia/Kolkata.")
    scheduler.start()