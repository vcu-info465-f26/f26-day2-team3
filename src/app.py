# The Streamlit frontend and the only program running live during the showcase.
# 1. Calls build_db.py at startup to load the latest snapshot.
# 2. Uses analyze.py to display tables and multi-month trend charts of FBS records.
# 3. Reads and displays data/summary.md.
# 4. Hosts the live LLM chat interface strictly for answering user questions


import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

st.set_page_config(page_title="ACC Standings Dashboard", layout="wide")


@st.cache_data
def load_data() -> pd.DataFrame:
    """Load every daily snapshot in data/ into one flat dataframe."""
    rows = []
    for path in sorted(DATA_DIR.glob("*.json")):
        with open(path) as f:
            payload = json.load(f)
        for s in payload.get("standings", []):
            conf_w, conf_l = s["conference_record"].split("-")
            rows.append(
                {
                    "date": path.stem,
                    "team": s["team"]["full_name"],
                    "abbr": s["team"]["abbreviation"],
                    "wins": s["wins"],
                    "losses": s["losses"],
                    "home_record": s["home_record"],
                    "away_record": s["away_record"],
                    "conference_record": s["conference_record"],
                    "conf_wins": int(conf_w),
                    "conf_losses": int(conf_l),
                    "games_behind": s["games_behind"],
                }
            )
    df = pd.DataFrame(rows)
    # the raw win_percentage field has nulls and bad values, so recompute it
    df["win_pct"] = (df["wins"] / (df["wins"] + df["losses"])).round(3)
    return df


def render_sidebar(df: pd.DataFrame) -> pd.DataFrame:
    """The ONE interactive filter. Returns the filtered dataframe."""
    st.sidebar.header("Filters")
    teams = sorted(df["team"].unique())
    selected = st.sidebar.multiselect("Teams", teams, default=teams)
    return df[df["team"].isin(selected)]


def latest_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["date"] == df["date"].max()]


def render_summary(df: pd.DataFrame) -> None:
    st.subheader("Summary")
    if df.empty:
        return
    latest = latest_snapshot(df)
    best = latest.sort_values(["win_pct", "wins"], ascending=False).iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Teams shown", latest["team"].nunique())
    c2.metric("Latest snapshot", df["date"].max())
    c3.metric("Best record", f"{best['team']} ({best['wins']}-{best['losses']})")


def render_record_chart(df: pd.DataFrame) -> None:
    st.subheader("Wins and losses (latest snapshot)")
    latest = latest_snapshot(df)
    long = latest.melt(
        id_vars=["team"], value_vars=["wins", "losses"],
        var_name="result", value_name="games",
    )
    fig = px.bar(long, x="team", y="games", color="result", barmode="group")
    st.plotly_chart(fig, width="stretch")


def render_trend_chart(df: pd.DataFrame) -> None:
    st.subheader("Wins over time")
    fig = px.line(df, x="date", y="wins", color="team", markers=True)
    st.plotly_chart(fig, width="stretch")


def render_plots(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Select at least one team in the sidebar.")
        return
    render_record_chart(df)
    render_trend_chart(df)


def render_table(df: pd.DataFrame) -> None:
    st.subheader("Standings data")
    cols = ["date", "team", "wins", "losses", "win_pct",
            "home_record", "away_record", "conference_record", "games_behind"]
    st.dataframe(df[cols], width="stretch", hide_index=True)


def main() -> None:
    st.title("ACC Standings Dashboard")
    df = load_data()
    filtered = render_sidebar(df)
    render_summary(filtered)
    render_plots(filtered)
    render_table(filtered)


if __name__ == "__main__":
    main()