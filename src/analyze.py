# Houses all SQLite database logic.
# Contains functions to query and JOIN the tables (e.g., matching teams to their conference standings).
# Keeps the frontend clean of raw SQL.
from pathlib import Path
import sqlite3


DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "bdl.db"


def get_conferences() -> list[tuple[str, int, str]]:
	with sqlite3.connect(DATABASE_PATH) as connection:
		return connection.execute(
			"SELECT name, id, abbreviation FROM conferences ORDER BY id"
		).fetchall()


if __name__ == "__main__":
	for conference in get_conferences():
		print(conference)
