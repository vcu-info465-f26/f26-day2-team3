from pathlib import Path
from io import BytesIO


import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
import pandas as pd
import streamlit as st


IMAGE_DIRECTORY = Path(__file__).resolve().parent.parent / "img"
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
TEAM_LOGOS = dict(zip(TEAM_COLORS, [
    "Boston_College_Eagles.png", "California_Golden_Bears.png",
    "Clemson_Tigers.png", "Duke_Blue_Devils.png", "Florida_State_Seminoles.png",
    "Georgia_Tech_Yellow_Jackets.png", "Louisville_Cardinals.png",
    "Miami_Hurricanes.png", "NC_State_Wolfpack.png", "North_Carolina_Tar_Heels.png",
    "Pittsburgh_Panthers.png", "SMU_Mustangs.png", "Stanford_Cardinal.png",
    "Syracuse_Orange.png", "Virginia_Cavaliers.png", "Virginia_Tech_Hokies.png",
    "Wake_Forest_Demon_Deacons.png",
], strict=True))
SEASON_PERIODS = [
    ("Week 1", (8, 22), (9, 7)), ("Week 2", (9, 8), (9, 13)),
    ("Week 3", (9, 14), (9, 20)), ("Week 4", (9, 21), (9, 27)),
    ("Week 5", (9, 28), (10, 4)), ("Week 6", (10, 5), (10, 11)),
    ("Week 7", (10, 12), (10, 18)), ("Week 8", (10, 19), (10, 25)),
    ("Week 9", (10, 26), (11, 1)), ("Week 10", (11, 2), (11, 8)),
    ("Week 11", (11, 9), (11, 15)), ("Week 12", (11, 16), (11, 22)),
    ("Week 13", (11, 23), (11, 29)), ("Week 14", (11, 30), (12, 6)),
    ("Week 15", (12, 7), (12, 12)), ("Bowls", (12, 13), (1, 27)),
]




def season_period_for_date(date: pd.Timestamp, season: int) -> str:
    for name, start, end in SEASON_PERIODS:
        start_date = pd.Timestamp(season, *start)
        end_date = pd.Timestamp(season + (end[0] < start[0]), *end)
        if start_date <= date <= end_date:
            return name
    return "Offseason"




def render_chart(chart: Figure) -> None:
    with BytesIO() as image:
        chart.savefig(image, format="png", dpi=140, bbox_inches=None)
        st.image(image.getvalue(), width="stretch")
    plt.close(chart)




@st.cache_data(show_spinner="Preparing the weekly standings timeline...")
def prepare_animation_history(
    history: pd.DataFrame, season: int, as_of: pd.Timestamp,
) -> pd.DataFrame:
    if history.empty:
        return history.copy()
    history = history.copy()
    history["snapshot_date"] = pd.to_datetime(history["snapshot_date"])
    snapshot_dates = []
    for _, start, end in SEASON_PERIODS:
        start_date = pd.Timestamp(season, *start)
        end_date = pd.Timestamp(season + (end[0] < start[0]), *end)
        if end_date >= as_of.normalize():
            continue
        week = history[history["snapshot_date"].between(start_date, end_date)]
        if not week.empty:
            snapshot_dates.append(week["snapshot_date"].max())
    snapshot_dates.append(history["snapshot_date"].max())
    return history[history["snapshot_date"].isin(snapshot_dates)].sort_values(
        ["snapshot_date", "rank"],
    ).reset_index(drop=True)




def standings_chart(
    history: pd.DataFrame, season: int, timeline_end: pd.Timestamp | None = None,
) -> Figure:
    history = history.copy()
    history["snapshot_date"] = pd.to_datetime(history["snapshot_date"])
    fig, ax = plt.subplots(figsize=(8, 5), dpi=140)
    ax.set_facecolor("#FAFAFC")
    fig.patch.set_facecolor("#FAFAFC")
    for _, team_history in history.groupby("team_id", sort=False):
        team_history = team_history.sort_values("snapshot_date")
        abbreviation = team_history["abbreviation"].iloc[0]
        primary, secondary, *tertiary = TEAM_COLORS[abbreviation]
        dates, ranks = team_history["snapshot_date"], team_history["rank"]
        ax.plot(dates, ranks, color=secondary, linewidth=4, alpha=0.9, zorder=2)
        ax.plot(dates, ranks, color=primary, linewidth=2.2, zorder=3)
        endpoint = (dates.iloc[-1], ranks.iloc[-1])
        ax.scatter(*endpoint, s=95, color=secondary,
                   edgecolors=tertiary[0] if tertiary else primary, linewidths=2, zorder=5)
        logo = plt.imread(IMAGE_DIRECTORY / TEAM_LOGOS[abbreviation])
        ax.add_artist(AnnotationBbox(
            OffsetImage(logo, zoom=0.035), endpoint, xybox=(16, 0),
            xycoords="data", boxcoords="offset points", frameon=False, pad=0,
        ))
    team_count = history["team_id"].nunique()
    last_date = timeline_end if timeline_end is not None else history["snapshot_date"].max()
    ax.set_xlim(history["snapshot_date"].min(), last_date + pd.Timedelta(days=3))
    ax.set_ylim(team_count + 0.7, 0.3)
    ax.set_yticks(range(1, team_count + 1))
    ax.set_ylabel("ACC Rank (1 = first)")
    ax.set_xlabel("Week / Snapshot Date")
    ax.set_title(f"{season} ACC Season Overview", loc="left", weight="bold", pad=16)
    snapshot_dates = sorted(history["snapshot_date"].unique())
    ax.set_xticks(
        mdates.date2num(snapshot_dates),
        [f"{season_period_for_date(pd.Timestamp(date), season)}\n{pd.Timestamp(date):%b %d}"
         for date in snapshot_dates],
        fontsize=8,
    )
    ax.grid(axis="both", color="#D8D8E0", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    return fig




def render_animation(snapshot_history: pd.DataFrame, season: int) -> None:
    st.subheader("ACC season overview")
    if snapshot_history.empty:
        st.info(f"No ACC standings history found for the {season} season yet.")
        return
    history = prepare_animation_history(snapshot_history, season, pd.Timestamp.today().normalize())
    if history.empty:
        st.info("No snapshots from completed football weeks are available yet.")
        return
    animation_dates = sorted(history["snapshot_date"].unique())
    # Reset when the season or available snapshots change to avoid stale frame indices.
    timeline_key = (season, tuple(animation_dates))
    if st.session_state.get("animation_timeline") != timeline_key:
        st.session_state.animation_timeline = timeline_key
        st.session_state.animation_index = len(animation_dates) - 1
        st.session_state.animation_playing = False
    play_column, pause_column = st.columns(2)
    with play_column:
        if st.button("Play", disabled=st.session_state.animation_playing, width="stretch"):
            if st.session_state.animation_index >= len(animation_dates) - 1:
                st.session_state.animation_index = 0
            st.session_state.animation_playing = True
    with pause_column:
        if st.button("Pause", disabled=not st.session_state.animation_playing, width="stretch"):
            st.session_state.animation_playing = False


    @st.fragment(run_every="1s" if st.session_state.animation_playing else None)
    def show_standings_animation() -> None:
        frame_index = st.session_state.animation_index
        snapshot_date = pd.Timestamp(animation_dates[frame_index])
        week = season_period_for_date(snapshot_date, season)
        st.caption(f"Snapshot: {snapshot_date:%b %d, %Y}  \n{week}")
        chart = standings_chart(
            history[history["snapshot_date"] <= snapshot_date], season,
            timeline_end=pd.Timestamp(animation_dates[-1]),
        )
        render_chart(chart)
        if st.session_state.animation_playing:
            if frame_index < len(animation_dates) - 1:
                st.session_state.animation_index = frame_index + 1
            else:
                st.session_state.animation_playing = False
                st.rerun()


    show_standings_animation()




def main() -> None:
    st.set_page_config(page_title="ACC FBS Standings", layout="wide")
    st.markdown(
        "<style>.block-container {padding-top: 1rem; padding-bottom: 1rem;}</style>",
        unsafe_allow_html=True,
    )
    st.title("2026 ACC FBS Standings")


    with st.spinner("Building database from the latest snapshot..."):
        build_db.main()


    season = 2026
    standings = analyze.get_conference_standings(season)


    if standings.empty:
        st.info(f"No ACC standings found for the {season} season yet.")
    else:
        history = get_standings_history(season)
        standings_column, animation_column = st.columns(2, gap="large")
        with standings_column, st.container(border=True):
            metric = render_standings(standings)
        with animation_column, st.container(border=True):
            render_animation(history, season)
        render_raw_standings(history, metric)




if __name__ == "__main__":
    main()