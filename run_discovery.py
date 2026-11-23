import logging
from dotenv import load_dotenv

from src.db import init_db
from src.discovery import discover_and_store
from src.profile import load_profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("data/discovery.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

if __name__ == "__main__":
    load_dotenv()
    init_db()
    profile = load_profile()
    target = int(profile.get("daily_discovery_target", 100))
    result = discover_and_store(profile, target)
    print(result["summary"])
    for error in result["errors"]:
        print("SOURCE ERROR:", error)