from datetime import datetime, timezone
import json
import os
import sqlite3
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = ROOT_DIR / "data" / "bdl.db"
load_dotenv(ROOT_DIR / ".env")


def save_snapshot(payload):
    DATA_DIR.mkdir(exist_ok=True)
    snapshot_path = DATA_DIR / f"{datetime.now(timezone.utc):%Y-%m-%d}.json"
    snapshot_path.write_text(json.dumps(payload, indent=2) + "\n")
    return snapshot_path


def get_conferences():
    api_key = os.getenv("BALLDONTLIE_API_KEY")
    if not api_key:
        raise RuntimeError("BALLDONTLIE_API_KEY is not configured")

    response = requests.get(
        "https://api.balldontlie.io/ncaaf/v1/conferences",
        headers={"Authorization": api_key},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    snapshot_path = save_snapshot(payload)
    print(f"Saved API snapshot to {snapshot_path}")
    return payload["data"]


def save_conferences(conferences):
    with sqlite3.connect(DB_PATH) as connection:
        connection.executemany(
            """
            INSERT INTO conferences (id, name, abbreviation)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                abbreviation = excluded.abbreviation
            """,
            [
                (
                    conference["id"],
                    conference["name"],
                    conference["abbreviation"],
                )
                for conference in conferences
            ],
        )
        connection.commit()


if __name__ == "__main__":
    conferences = get_conferences()
    save_conferences(conferences)
    print(f"Saved {len(conferences)} conferences to {DB_PATH}")