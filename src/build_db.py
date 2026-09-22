from pathlib import Path
import json
import sqlite3


DATABASE_DIR = Path(__file__).resolve().parent.parent / "data"
DATABASE_PATH = DATABASE_DIR / "bdl.db"

def create_conferences_database() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conferences (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                abbreviation TEXT NOT NULL UNIQUE
            );
            """
        )
def create_teams_database() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(teams)")
        }
        if "college" in columns and "city" not in columns:
            connection.execute("ALTER TABLE teams RENAME TO teams_legacy")
            connection.execute(
                """
                CREATE TABLE teams (
                    id INTEGER PRIMARY KEY,
                    conference_id INTEGER NOT NULL,
                    city TEXT NOT NULL,
                    name TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    abbreviation TEXT NOT NULL,
                    UNIQUE (conference_id, abbreviation)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO teams
                    (id, conference_id, city, name, full_name, abbreviation)
                SELECT
                    id, conference_id, college, name, full_name, abbreviation
                FROM teams_legacy
                """
            )
            connection.execute("DROP TABLE teams_legacy")

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY,
                conference_id INTEGER NOT NULL,
                city TEXT NOT NULL,
                name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                abbreviation TEXT NOT NULL,
                UNIQUE (conference_id, abbreviation)
            );

            CREATE INDEX IF NOT EXISTS idx_teams_conference_id
                ON teams (conference_id);
            """
        )


def create_standings_database() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(standings)")
        }
        if columns and "snapshot_date" not in columns:
            connection.execute("ALTER TABLE standings RENAME TO standings_legacy")
            connection.execute(
                """
                CREATE TABLE standings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id INTEGER NOT NULL,
                    conference_id INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    snapshot_date TEXT NOT NULL,
                    wins INTEGER,
                    losses INTEGER,
                    win_percentage REAL,
                    games_behind REAL,
                    home_record TEXT,
                    away_record TEXT,
                    conference_record TEXT,
                    UNIQUE (team_id, season, snapshot_date)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO standings (
                    id, team_id, conference_id, season, snapshot_date,
                    wins, losses, win_percentage, games_behind, home_record,
                    away_record, conference_record
                )
                SELECT
                    id, team_id, conference_id, season, 'legacy', wins, losses,
                    win_percentage, games_behind, home_record, away_record,
                    conference_record
                FROM standings_legacy
                """
            )
            connection.execute("DROP TABLE standings_legacy")

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS standings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                conference_id INTEGER NOT NULL,
                season INTEGER NOT NULL,
                snapshot_date TEXT NOT NULL,
                wins INTEGER,
                losses INTEGER,
                win_percentage REAL,
                games_behind REAL,
                home_record TEXT,
                away_record TEXT,
                conference_record TEXT,
                UNIQUE (team_id, season, snapshot_date)
            );

            CREATE INDEX IF NOT EXISTS idx_standings_conference_season
                ON standings (conference_id, season);
            """
        )


def _snapshot_records(payload: dict) -> list[dict]:
    records = payload.get("data", payload)
    if isinstance(records, dict):
        return [record for value in records.values() if isinstance(value, list) for record in value]
    return records if isinstance(records, list) else []


def _conference_id(record: dict):
    conference = record.get("conference_id", record.get("conference"))
    if isinstance(conference, dict):
        return conference.get("id")
    return conference


def _load_snapshots(connection: sqlite3.Connection) -> None:
    for snapshot_path in sorted(DATABASE_DIR.glob("*.json")):
        payload = json.loads(snapshot_path.read_text())
        snapshot_date = snapshot_path.stem

        for record in _snapshot_records(payload):
            team = record.get("team", record)
            if "wins" in record and isinstance(team, dict) and "id" in team:
                conference_id = _conference_id(team)
                if conference_id != 1:
                    continue
                connection.execute(
                    """
                    INSERT INTO teams
                        (id, conference_id, city, name, full_name, abbreviation)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        conference_id = excluded.conference_id,
                        city = excluded.city,
                        name = excluded.name,
                        full_name = excluded.full_name,
                        abbreviation = excluded.abbreviation
                    """,
                    (
                        team["id"], conference_id, team.get("city", team.get("college", "")),
                        team["name"], team["full_name"], team["abbreviation"],
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO standings (
                        team_id, conference_id, season, snapshot_date, wins, losses,
                        win_percentage, games_behind, home_record, away_record,
                        conference_record
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(team_id, season, snapshot_date) DO UPDATE SET
                        conference_id = excluded.conference_id,
                        wins = excluded.wins,
                        losses = excluded.losses,
                        win_percentage = excluded.win_percentage,
                        games_behind = excluded.games_behind,
                        home_record = excluded.home_record,
                        away_record = excluded.away_record,
                        conference_record = excluded.conference_record
                    """,
                    (
                        team["id"], conference_id, record.get("season", int(snapshot_date[:4])),
                        snapshot_date, record.get("wins"), record.get("losses"),
                        record.get("win_percentage"), record.get("games_behind"),
                        record.get("home_record"), record.get("away_record"),
                        record.get("conference_record"),
                    ),
                )
                continue

            if (
                {"id", "name", "full_name", "abbreviation"}.issubset(record)
                and _conference_id(record) == 1
            ):
                connection.execute(
                    """
                    INSERT INTO teams
                        (id, conference_id, city, name, full_name, abbreviation)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        conference_id = excluded.conference_id,
                        city = excluded.city,
                        name = excluded.name,
                        full_name = excluded.full_name,
                        abbreviation = excluded.abbreviation
                    """,
                    (
                        record["id"], _conference_id(record), record.get("city", record.get("college", "")),
                        record["name"], record["full_name"], record["abbreviation"],
                    ),
                )
                continue

            if {"id", "name", "abbreviation"}.issubset(record):
                connection.execute(
                    """
                    INSERT INTO conferences (id, name, abbreviation)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        abbreviation = excluded.abbreviation
                    """,
                    (record["id"], record["name"], record["abbreviation"]),
                )


def _print_database_summary() -> None:
    with sqlite3.connect(DATABASE_PATH) as connection:
        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        print("Tables and row counts:")
        for (table_name,) in tables:
            row_count = connection.execute(
                f'SELECT COUNT(*) FROM "{table_name}"'
            ).fetchone()[0]
            print(f"- {table_name}: {row_count} rows")


def main() -> None:
    DATABASE_DIR.mkdir(exist_ok=True)
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    create_conferences_database()
    create_teams_database()
    create_standings_database()
    with sqlite3.connect(DATABASE_PATH) as connection:
        _load_snapshots(connection)
    print(f"Created SQLite database at {DATABASE_PATH}")
    _print_database_summary()


if __name__ == "__main__":
    main()