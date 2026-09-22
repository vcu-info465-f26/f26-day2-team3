# Houses all SQLite database logic.
# Contains functions to query and JOIN the tables (e.g., matching teams to their conference standings).
# Keeps the frontend clean of raw SQL.
from pathlib import Path
import argparse
import sqlite3

import pandas as pd


DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "bdl.db"


STANDINGS_COLUMNS = [
	"team_id",
	"season",
	"snapshot_date",
	"conference",
	"city",
	"name",
	"abbreviation",
	"wins",
	"losses",
	"win_percentage",
	"games_behind",
	"home_record",
	"away_record",
	"conference_record",
]


def get_conference_standings(season: int) -> pd.DataFrame:
	"""Return the latest ACC standings snapshot for a season."""
	read_only_uri = f"file:{DATABASE_PATH}?mode=ro"
	with sqlite3.connect(read_only_uri, uri=True) as connection:
		standings = pd.read_sql_query(
			"""
			SELECT team_id, season, snapshot_date, wins, losses,
			       win_percentage, games_behind, home_record, away_record,
			       conference_record
			FROM standings
			WHERE conference_id = 1 AND season = ? AND snapshot_date <> 'legacy'
			""",
			connection,
			params=(season,),
		)
		teams = pd.read_sql_query(
			"""
			SELECT id AS team_id, city, name, abbreviation
			FROM teams
			WHERE conference_id = 1
			""",
			connection,
		)
		conferences = pd.read_sql_query(
			"""
			SELECT id AS conference_id, name AS conference
			FROM conferences
			WHERE id = 1
			""",
			connection,
		)

	if standings.empty:
		return pd.DataFrame(columns=STANDINGS_COLUMNS)

	latest_snapshot = standings["snapshot_date"].max()
	standings = standings[standings["snapshot_date"] == latest_snapshot]
	standings["conference_id"] = 1
	result = (
		standings.merge(teams, on="team_id", how="inner")
		.merge(conferences, on="conference_id", how="inner")
		.loc[:, STANDINGS_COLUMNS]
		.sort_values(["wins", "losses", "city"], ascending=[False, True, True])
		.reset_index(drop=True)
	)
	return result


def get_conferences() -> list[tuple[str, int, str]]:
	with sqlite3.connect(DATABASE_PATH) as connection:
		return connection.execute(
			"SELECT name, id, abbreviation FROM conferences ORDER BY id"
		).fetchall()


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Show the latest ACC standings.")
	parser.add_argument("--season", type=int, default=2026)
	args = parser.parse_args()

	standings = get_conference_standings(args.season)
	if standings.empty:
		print(f"No ACC standings found for the {args.season} season.")
	else:
		print(standings.to_string(index=False))
