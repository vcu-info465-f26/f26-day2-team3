from pathlib import Path
import sys

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIRECTORY = Path(__file__).resolve().parent
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

import analyze
import build_db

IMAGE_DIRECTORY = PROJECT_ROOT / "img"

TEAM_COLORS = {
    "BC": ("#8A100B", "#BC9B6A"),
    "CAL": ("#003262", "#FDB515"),
    "CLEM": ("#F56600", "#522D80"),
    "DUKE": ("#00539B", "#FFFFFF"),
    "FSU": ("#782F40", "#CEB888"),
    "GT": ("#B3A369", "#003057", "#FFFFFF"),
    "LOU": ("#AD0000", "#000000", "#FFFFFF"),
    "MIA": ("#F47321", "#005030", "#FFFFFF"),
    "NCSU": ("#CC0000", "#000000", "#FFFFFF"),
    "UNC": ("#7BAFD4", "#FFFFFF", "#13294B"),
    "PITT": ("#003594", "#FFB81C"),
    "SMU": ("#CC0035", "#354CA1"),
    "STAN": ("#8C1515", "#FFFFFF"),
    "SYR": ("#F76900", "#000E54"),
    "UVA": ("#E57200", "#232D4B"),
    "VT": ("#861F41", "#E5751F"),
    "WAKE": ("#9E7E38", "#000000"),
}

TEAM_LOGOS = {
    "BC": "Boston_College_Eagles.png",
    "CAL": "California_Golden_Bears.png",
    "CLEM": "Clemson_Tigers.png",
    "DUKE": "Duke_Blue_Devils.png",
    "FSU": "Florida_State_Seminoles.png",
    "GT": "Georgia_Tech_Yellow_Jackets.png",
    "LOU": "Louisville_Cardinals.png",
    "MIA": "Miami_Hurricanes.png",
    "NCSU": "NC_State_Wolfpack.png",
    "UNC": "North_Carolina_Tar_Heels.png",
    "PITT": "Pittsburgh_Panthers.png",
    "SMU": "SMU_Mustangs.png",
    "STAN": "Stanford_Cardinal.png",
    "SYR": "Syracuse_Orange.png",
    "UVA": "Virginia_Cavaliers.png",
    "VT": "Virginia_Tech_Hokies.png",
    "WAKE": "Wake_Forest_Demon_Deacons.png",
}

SEASON_PERIODS = [
    ("Week 1", (8, 22), (9, 7)),
    ("Week 2", (9, 8), (9, 13)),
    ("Week 3", (9, 14), (9, 20)),
    ("Week 4", (9, 21), (9, 27)),
    ("Week 5", (9, 28), (10, 4)),
    ("Week 6", (10, 5), (10, 11)),
    ("Week 7", (10, 12), (10, 18)),
    ("Week 8", (10, 19), (10, 25)),
    ("Week 9", (10, 26), (11, 1)),
    ("Week 10", (11, 2), (11, 8)),
    ("Week 11", (11, 9), (11, 15)),
    ("Week 12", (11, 16), (11, 22)),
    ("Week 13", (11, 23), (11, 29)),
    ("Week 14", (11, 30), (12, 6)),
    ("Week 15", (12, 7), (12, 12)),
    ("Bowls", (12, 13), (1, 27)),
]


def season_period_for_date(date: pd.Timestamp, season: int) -> str:
    for name, start, end in SEASON_PERIODS:
        start_date = pd.Timestamp(season, start[0], start[1])
        end_year = season + (end[0] < start[0])
        end_date = pd.Timestamp(end_year, end[0], end[1])
        if start_date <= date <= end_date:
            return name
    return "Offseason"


@st.cache_data(show_spinner="Preparing the daily standings timeline...")
def prepare_animation_history(history: pd.DataFrame) -> pd.DataFrame:
    history = history.copy()
    history["snapshot_date"] = pd.to_datetime(history["snapshot_date"])
    daily_dates = pd.date_range(
        history["snapshot_date"].min(),
        history["snapshot_date"].max(),
        freq="D",
    )
    daily_team_histories = []

    for _, team_history in history.groupby("team_id", sort=False):
        team_history = team_history.sort_values("snapshot_date").set_index("snapshot_date")
        team_history = team_history.reindex(daily_dates)
        team_history["rank"] = team_history["rank"].interpolate(
            method="time"
        ).ffill().bfill()
        team_history = team_history.ffill().bfill()
        team_history["snapshot_date"] = daily_dates
        daily_team_histories.append(team_history.reset_index(drop=True))

    return pd.concat(daily_team_histories, ignore_index=True)


def standings_chart(
    history: pd.DataFrame,
    season: int,
    timeline_end: pd.Timestamp | None = None,
) -> plt.Figure:
    history = history.copy()
    history["snapshot_date"] = pd.to_datetime(history["snapshot_date"])
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_facecolor("#FAFAFC")
    fig.patch.set_facecolor("#FAFAFC")

    for _, team_history in history.groupby("team_id", sort=False):
        team_history = team_history.sort_values("snapshot_date")
        team_history = team_history.set_index("snapshot_date")
        full_dates = pd.date_range(
            team_history.index.min(),
            team_history.index.max(),
            freq="D",
        )
        team_history = team_history.reindex(full_dates).ffill().bfill()
        team_history = team_history.reset_index().rename(columns={"index": "snapshot_date"})

        abbreviation = team_history["abbreviation"].iloc[0]
        primary, secondary, *tertiary = TEAM_COLORS[abbreviation]
        dates = pd.to_datetime(team_history["snapshot_date"])
        ranks = team_history["rank"]
        ax.plot(dates, ranks, color=secondary, linewidth=4, alpha=0.9, zorder=2)
        ax.plot(dates, ranks, color=primary, linewidth=2.2, zorder=3)

        final_date = dates.iloc[-1]
        final_rank = ranks.iloc[-1]
        ax.scatter(
            final_date,
            final_rank,
            s=95,
            color=secondary,
            edgecolors=tertiary[0] if tertiary else primary,
            linewidths=2,
            zorder=5,
        )
        logo = plt.imread(IMAGE_DIRECTORY / TEAM_LOGOS[abbreviation])
        logo_box = AnnotationBbox(
            OffsetImage(logo, zoom=0.06),
            (final_date, final_rank),
            xybox=(24, 0),
            xycoords="data",
            boxcoords="offset points",
            frameon=False,
            pad=0,
        )
        ax.add_artist(logo_box)

    team_count = int(history["rank"].max())
    first_date = history["snapshot_date"].min()
    last_date = timeline_end or history["snapshot_date"].max()
    ax.set_xlim(first_date, last_date + pd.Timedelta(days=3))
    ax.set_ylim(team_count + 0.7, 0.3)
    ax.set_yticks(range(1, team_count + 1))
    ax.set_ylabel("ACC rank (1 = first)")
    ax.set_xlabel("Snapshot date")
    ax.set_title(f"{season} ACC Season Overview", loc="left", weight="bold", pad=16)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=9))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.grid(axis="both", color="#D8D8E0", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig


st.set_page_config(page_title="ACC FBS Standings", layout="wide")
st.title("ACC FBS Standings")

with st.spinner("Building database from the latest snapshot..."):
    build_db.main()

season = st.number_input("Season", min_value=2000, max_value=2100, value=2026, step=1)

standings = analyze.get_conference_standings(int(season))

if standings.empty:
    st.info(f"No ACC standings found for the {season} season yet.")
else:
    snapshot_history = analyze.get_standings_history(int(season))
    if snapshot_history.empty:
        st.info(f"No ACC standings history found for the {season} season yet.")
        st.dataframe(standings, width="stretch")
        st.stop()

    history = prepare_animation_history(snapshot_history)
    animation_dates = history["snapshot_date"].drop_duplicates().to_numpy()
    if st.session_state.get("animation_season") != int(season):
        st.session_state.animation_season = int(season)
        st.session_state.animation_index = len(animation_dates) - 1
        st.session_state.animation_playing = False

    play_column, pause_column = st.columns(2)
    with play_column:
        if st.button(
            "▶ Play",
            disabled=st.session_state.get("animation_playing", False),
            use_container_width=True,
        ):
            if st.session_state.animation_index >= len(animation_dates) - 1:
                st.session_state.animation_index = 0
            st.session_state.animation_playing = True
    with pause_column:
        if st.button(
            "⏸ Pause",
            disabled=not st.session_state.get("animation_playing", False),
            use_container_width=True,
        ):
            st.session_state.animation_playing = False

    @st.fragment(
        run_every="1s" if st.session_state.get("animation_playing", False) else None
    )
    def show_standings_animation() -> None:
        frame_index = st.session_state.animation_index
        snapshot_date = pd.Timestamp(animation_dates[frame_index])
        visible_history = history[history["snapshot_date"] <= snapshot_date]
        week = season_period_for_date(snapshot_date, int(season))
        st.caption(
            f"{week} · {snapshot_date:%b} {snapshot_date.day}, {snapshot_date.year}"
        )
        chart = standings_chart(
            visible_history,
            int(season),
            timeline_end=pd.Timestamp(animation_dates[-1]),
        )
        st.pyplot(chart)
        plt.close(chart)

        if st.session_state.animation_playing:
            if frame_index < len(animation_dates) - 1:
                st.session_state.animation_index = frame_index + 1
            else:
                st.session_state.animation_playing = False
                st.rerun()

    show_standings_animation()
    st.dataframe(standings, width="stretch")