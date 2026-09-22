import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
BASE_URL = "https://api.balldontlie.io/ncaaf/v1"
ACC_ID = 1
REQUEST_TIMEOUT = 30
MAX_ATTEMPTS = 3
MIN_REQUEST_INTERVAL = 12
load_dotenv(ROOT_DIR / ".env")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(self, api_key):
        self.session = requests.Session()
        self.session.headers.update({"Authorization": api_key})
        self.last_request_at = 0.0

    def get_page(self, endpoint, params):
        for attempt in range(MAX_ATTEMPTS):
            wait = MIN_REQUEST_INTERVAL - (time.monotonic() - self.last_request_at)
            if wait > 0:
                time.sleep(wait)

            try:
                logger.info("Requesting /%s with params %s", endpoint, params)
                response = self.session.get(
                    f"{BASE_URL}/{endpoint}",
                    params=params,
                    timeout=REQUEST_TIMEOUT,
                )
                self.last_request_at = time.monotonic()
            except requests.RequestException as exc:
                if attempt == MAX_ATTEMPTS - 1:
                    raise RuntimeError(
                        f"Network error requesting /{endpoint} after "
                        f"{MAX_ATTEMPTS} attempts: {exc}"
                    ) from exc
                logger.warning(
                    "Network error requesting /%s; retrying attempt %d/%d: %s",
                    endpoint,
                    attempt + 2,
                    MAX_ATTEMPTS,
                    exc,
                )
                time.sleep(2**attempt)
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == MAX_ATTEMPTS - 1:
                    response.raise_for_status()
                logger.warning(
                    "HTTP %s from /%s; retrying attempt %d/%d",
                    response.status_code,
                    endpoint,
                    attempt + 2,
                    MAX_ATTEMPTS,
                )
                time.sleep(2**attempt)
                continue

            if 400 <= response.status_code < 500:
                raise RuntimeError(
                    f"API request /{endpoint} failed with HTTP "
                    f"{response.status_code}: {response.text[:200]}"
                )

            response.raise_for_status()
            logger.info("Received HTTP %s from /%s", response.status_code, endpoint)
            return response.json()

        raise RuntimeError(f"API request /{endpoint} failed")

    def get_all(self, endpoint, params):
        records = []
        page_params = dict(params)
        page_number = 1
        while True:
            payload = self.get_page(endpoint, page_params)
            page_records = payload.get("data", [])
            records.extend(page_records)
            logger.info(
                "Fetched page %d from /%s: %d records",
                page_number,
                endpoint,
                len(page_records),
            )
            next_cursor = payload.get("meta", {}).get("next_cursor")
            if not next_cursor:
                logger.info("Finished /%s: %d total records", endpoint, len(records))
                return records
            page_params["cursor"] = next_cursor
            page_number += 1


def save_snapshot(payload):
    DATA_DIR.mkdir(exist_ok=True)
    snapshot_path = DATA_DIR / f"{datetime.now(timezone.utc):%Y-%m-%d}.json"
    if snapshot_path.exists():
        logger.info("Snapshot already exists; skipping write: %s", snapshot_path)
        return None
    snapshot_path.write_text(json.dumps(payload, indent=2) + "\n")
    logger.info("Created JSON snapshot: %s", snapshot_path)
    return snapshot_path


def filter_acc_conferences(conferences):
    return [
        conference
        for conference in conferences
        if (
            conference.get("id") == ACC_ID
            and conference.get("name") == "ACC"
            and conference.get("abbreviation") == "ACC"
        )
    ]


def filter_acc_teams(teams):
    return [team for team in teams if team.get("conference") == ACC_ID]


def filter_acc_standings(standings):
    return [
        standing
        for standing in standings
        if standing.get("conference", {}).get("id") == ACC_ID
    ]


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch ACC NCAAF data as JSON")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--api-key", default=os.getenv("BALLDONTLIE_API_KEY"))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if not args.api_key:
        raise SystemExit(
            "Error: an API key is required. Set BALLDONTLIE_API_KEY or pass --api-key."
        )
    today_snapshot = DATA_DIR / f"{datetime.now(timezone.utc):%Y-%m-%d}.json"
    if today_snapshot.exists():
        logger.info(
            "Today's snapshot already exists at %s; skipping API requests.",
            today_snapshot,
        )
        raise SystemExit(0)

    logger.info("Starting ACC data fetch for season %d", args.season)
    client = ApiClient(args.api_key)
    conferences = filter_acc_conferences(
        client.get_all("conferences", {"id": ACC_ID})
    )
    teams = filter_acc_teams(
        client.get_all("teams", {"conference_id": ACC_ID})
    )
    standings = filter_acc_standings(
        client.get_all(
            "standings", {"season": args.season, "conference_id": ACC_ID}
        )
    )
    snapshot_path = save_snapshot(
        {"conferences": conferences, "teams": teams, "standings": standings}
    )
    if snapshot_path is not None:
        print(f"Saved ACC JSON snapshot to {snapshot_path}")
