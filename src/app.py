import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

SRC_DIRECTORY = Path(__file__).resolve().parent
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

import build_db

ROOT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = ROOT_DIR / "data" / "bdl.db"


@st.cache_resource
def initialize_database() -> None:
    build_db.main()


@st.cache_data
def load_latest_standings(database_path: str) -> pd.DataFrame:
    with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
        return pd.read_sql_query(
            """
            WITH latest AS (
                SELECT season, MAX(snapshot_date) AS snapshot_date
                FROM standings
                WHERE conference_id = 1 AND snapshot_date <> 'legacy'
                GROUP BY season
                ORDER BY season DESC
                LIMIT 1
            )
            SELECT teams.city AS team, teams.abbreviation, standings.wins,
                   standings.losses, standings.win_percentage,
                   standings.conference_record, standings.season,
                   standings.snapshot_date
            FROM standings
            JOIN teams ON teams.id = standings.team_id
            JOIN latest ON latest.season = standings.season
                        AND latest.snapshot_date = standings.snapshot_date
            WHERE standings.conference_id = 1
            ORDER BY teams.city
            """,
            connection,
        )


def filter_standings(standings: pd.DataFrame, teams: list[str]) -> pd.DataFrame:
    return standings[standings["team"].isin(teams)].sort_values(
        ["wins", "losses", "team"],
        ascending=[False, True, True],
    )


def render_chart(standings: pd.DataFrame, metric: str) -> None:
    st.subheader(metric.title())
    st.bar_chart(standings, x="team", y=metric, horizontal=True)


def render_dashboard() -> None:
    standings = load_latest_standings(str(DATABASE_PATH))
    if standings.empty:
        st.warning("No ACC standings are available in the repository snapshots.")
        return

    season = int(standings["season"].iloc[0])
    snapshot_date = standings["snapshot_date"].iloc[0]
    st.caption(f"{season} season · Latest update {snapshot_date}")

    teams = sorted(standings["team"].tolist())
    selected_teams = st.multiselect("Teams", teams, default=teams)
    filtered = filter_standings(standings, selected_teams)

    wins_column, losses_column = st.columns(2)
    with wins_column:
        render_chart(filtered, "wins")
    with losses_column:
        render_chart(filtered, "losses")

    st.subheader("Standings")
    st.dataframe(filtered, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="ACC FBS Standings", layout="wide")
    st.title("ACC FBS Standings")
    with st.spinner("Preparing standings..."):
        initialize_database()
    render_dashboard()


if __name__ == "__main__":
    main()
