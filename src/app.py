from pathlib import Path
from io import BytesIO

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.ticker import MaxNLocator
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


def make_standings_chart(standings: pd.DataFrame, metric: str) -> Figure:
    other_metric = "losses" if metric == "wins" else "wins"
    standings = standings.sort_values(
        [metric, other_metric, "city"], ascending=[False, True, True],
    ).reset_index(drop=True)
    fig, axis = plt.subplots(figsize=(8, 5), dpi=140)
    fig.patch.set_facecolor("white")
    axis.set_facecolor("white")
    for position, row in standings.iterrows():
        abbreviation = row["abbreviation"]
        primary, secondary, *_ = TEAM_COLORS[abbreviation]
        value = int(row[metric])
        axis.barh(position, value, color=primary, edgecolor=secondary,
                  linewidth=2, height=0.62, zorder=2)
        logo_path = IMAGE_DIRECTORY / TEAM_LOGOS[abbreviation]
        if logo_path.exists():
            axis.add_artist(AnnotationBbox(
                OffsetImage(plt.imread(logo_path), zoom=0.03),
                (max(value - 0.25, 0.18), position), frameon=True, pad=0.08,
                bboxprops={"facecolor": "white", "edgecolor": secondary, "linewidth": 1.2},
                zorder=3,
            ))
        axis.text(value + 0.45, position, str(value),
                  va="center", ha="left", color="#242424", fontsize=10)
    axis.set_yticks(range(len(standings)), standings["city"], fontsize=9)
    axis.invert_yaxis()
    axis.set_xlim(0, max(standings[metric].max() + 1.7, 2))
    axis.xaxis.set_ticks_position("top")
    axis.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
    axis.tick_params(axis="x", colors="#7A7A7A", labelsize=9, length=0, pad=9)
    axis.tick_params(axis="y", colors="#262626", length=0, pad=10)
    axis.grid(axis="x", color="#E8E8E8", linewidth=0.8, zorder=0)
    axis.set_axisbelow(True)
    for spine in axis.spines.values():
        spine.set_visible(False)
    fig.subplots_adjust(left=0.26, right=0.96, top=0.94, bottom=0.035)
    return fig


def render_standings(standings: pd.DataFrame) -> str:
    st.subheader("Wins and losses")
    selection = st.selectbox("Sort teams by", ["Wins", "Losses"], label_visibility="collapsed")
    st.caption(
        f"{standings['season'].iloc[0]} season | "
        f"Snapshot: {standings['snapshot_date'].iloc[0]} | {len(standings)} teams  \n"
        f"{season_period_for_date(pd.Timestamp(standings['snapshot_date'].iloc[0]), int(standings['season'].iloc[0]))}"
    )
    chart = make_standings_chart(standings, selection.lower())
    render_chart(chart)
    return selection.lower()


def render_raw_standings(history: pd.DataFrame, metric: str) -> None:
    table = history.sort_values(
        ["snapshot_date", metric, "city"], ascending=[False, False, True],
    ).copy()
    table.insert(
        table.columns.get_loc("snapshot_date") + 1, "week",
        [season_period_for_date(pd.Timestamp(date), int(season))
         for date, season in zip(table["snapshot_date"], table["season"])],
    )
    with st.container(border=True):
        st.subheader("Raw standings data")
        st.dataframe(table, width="stretch", hide_index=True)
