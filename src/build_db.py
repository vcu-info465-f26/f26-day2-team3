from pathlib import Path
import sqlite3


DATABASE_DIR = Path(__file__).resolve().parent.parent / "data"
DATABASE_PATH = DATABASE_DIR / "bdl.db"

CONFERENCES = [
    (10, "SEC", "SEC"),
    (4, "Big Ten", "Big Ten"),
    (3, "Big 12", "Big 12"),
    (1, "ACC", "ACC"),
    (6, "FBS Indep.", "FBS Indep."),
    (9, "PAC 12", "Pac-12"),
    (2, "American", "American"),
    (11, "Sun Belt", "Sun Belt"),
    (8, "Mountain West", "Mountain West"),
    (7, "MAC", "MAC"),
]


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
        connection.executemany(
            """
            INSERT INTO conferences (id, name, abbreviation)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                abbreviation = excluded.abbreviation;
            """,
            CONFERENCES,
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


def main() -> None:
    DATABASE_DIR.mkdir(exist_ok=True)
    create_conferences_database()
    create_teams_database()
    create_standings_database()
    print(f"Created SQLite database at {DATABASE_PATH}")


if __name__ == "__main__":
    main()