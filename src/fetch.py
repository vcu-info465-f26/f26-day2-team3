# Runs on a GitHub Actions schedule.
# Fetches live NCAAF data from the balldontlie endpoints (conferences, teams, standings)
# Writes output to a dated snapshot (e.g., data/2026-09-10.json).import os
import os
import sqlite3
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "data" / "bdl.db"
load_dotenv(ROOT_DIR / ".env")


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
    return response.json()["data"]


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