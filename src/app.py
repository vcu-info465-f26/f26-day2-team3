from pathlib import Path
from io import BytesIO
from concurrent.futures import Future, ThreadPoolExecutor
import json
import re

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.ticker import MaxNLocator
import pandas as pd
from PIL import Image
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates

import analyze
import build_db
import chat

CHAT_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chat")

IMAGE_DIRECTORY = Path(__file__).resolve().parent.parent / "img"
SUMMARY_PATH = Path(__file__).resolve().parent.parent / "data" / "summary.md"
BOXSCORE_DIRECTORY = Path(__file__).resolve().parent.parent / "boxscore"
NEUTRAL_LINE_COLOR = "#C9C9D3"
DOT_CLICK_RADIUS = 18
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
    ("Preseason", (8, 1), (8, 28)),
    ("Week 1", (8, 29), (9, 7)), ("Week 2", (9, 8), (9, 13)),
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


def chart_image(chart: Figure) -> bytes:
    with BytesIO() as image:
        chart.savefig(image, format="png", dpi=140, bbox_inches=None)
        plt.close(chart)
        return image.getvalue()


def render_chart(chart: Figure) -> None:
    st.image(chart_image(chart), width="stretch")


def game_date(game: dict) -> pd.Timestamp:
    start = pd.Timestamp(game["startDate"])
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    return start.tz_convert("America/New_York").tz_localize(None).normalize()


def team_box_scores(school: str, week: str, season: int) -> list[dict]:
    box_scores = []
    for path in BOXSCORE_DIRECTORY.glob("*.json"):
        box_score = json.loads(path.read_text(encoding="utf-8"))
        game = box_score["game"]
        teams = {game["homeTeam"].casefold(), game["awayTeam"].casefold()}
        if school.casefold() in teams and season_period_for_date(game_date(game), season) == week:
            box_scores.append(box_score)
    return sorted(box_scores, key=lambda box_score: box_score["game"]["startDate"])


def readable(label: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", " ", label).replace("_", " ").title()


def pick(entry: dict, *path: str):
    for key in path:
        if not isinstance(entry, dict):
            return None
        entry = entry.get(key)
    return entry


TEAM_METRICS = [
    ("ppa", "Plays", "plays"),
    ("ppa", "PPA per play", "overall", "total"),
    ("ppa", "Passing PPA per play", "passing", "total"),
    ("ppa", "Rushing PPA per play", "rushing", "total"),
    ("cumulativePpa", "Total PPA", "overall", "total"),
    ("successRates", "Success rate", "overall", "total"),
    ("successRates", "Standard downs success rate", "standardDowns", "total"),
    ("successRates", "Passing downs success rate", "passingDowns", "total"),
    ("explosiveness", "Explosiveness", "overall", "total"),
    ("rushing", "Line yards per rush", "lineYardsAverage"),
    ("rushing", "Stuff rate", "stuffRate"),
    ("rushing", "Power success", "powerSuccess"),
    ("havoc", "Havoc rate", "total"),
    ("scoringOpportunities", "Scoring opportunities", "opportunities"),
    ("scoringOpportunities", "Points per opportunity", "pointsPerOpportunity"),
    ("fieldPosition", "Average starting field position", "averageStart"),
]
PLAYER_SECTIONS = [
    ("passing", [("Att", "attempts"), ("Cmp", "completions"), ("Yds", "totalYards"),
                 ("Int", "interceptions"), ("Cmp %", "completionRate"), ("PPA", "ppa")]),
    ("rushing", [("Att", "attempts"), ("Yds", "totalRushingYards"), ("YPC", "yardsPerCarry"),
                 ("Success rate", "successRate"), ("PPA", "ppa")]),
    ("usage", [("Pos", "position"), ("Usage", "total"), ("Passing", "passing"), ("Rushing", "rushing")]),
    ("ppa", [("Pos", "position"), ("Avg PPA", "average", "total"), ("Total PPA", "cumulative", "total")]),
]


def render_box_score(box_score: dict) -> None:
    game = box_score["game"]
    away, home = game["awayTeam"], game["homeTeam"]
    st.markdown(f"### {away} {game.get('awayPoints')} @ {home} {game.get('homePoints')}")
    venue = f" | {game['venue']}" if game.get("venue") else ""
    st.caption(f"{game_date(game):%a, %b %d, %Y}{venue}")

    away_lines, home_lines = game.get("awayLineScores"), game.get("homeLineScores")
    if away_lines and home_lines and len(away_lines) == len(home_lines):
        periods = [f"Q{number}" if number <= 4 else f"OT{number - 4}"
                   for number in range(1, len(away_lines) + 1)]
        line_score = pd.DataFrame([away_lines, home_lines], index=[away, home], columns=periods)
        line_score["Final"] = [game.get("awayPoints"), game.get("homePoints")]
        st.dataframe(line_score, width="stretch")

    advanced = box_score.get("advanced") or {}
    game_info = advanced.get("gameInfo") or {}
    if game_info:
        away_probability, home_probability = pick(game_info, "awayWinProb"), pick(game_info, "homeWinProb")
        probability = (
            f" | Win probability: {away} {away_probability:.0%}, {home} {home_probability:.0%}"
            if isinstance(away_probability, (int, float)) and isinstance(home_probability, (int, float))
            else ""
        )
        st.caption(f"Excitement index: {pick(game_info, 'excitement')}{probability}")

    team_metrics = {}
    for section, label, *path in TEAM_METRICS:
        for entry in (advanced.get("teams") or {}).get(section) or []:
            team_metrics.setdefault(label, {})[entry["team"]] = pick(entry, *path)
    if team_metrics:
        st.markdown("**Team advanced stats**")
        st.dataframe(pd.DataFrame(team_metrics).T.round(3), width="stretch")

    players = advanced.get("players") or {}
    player_teams = sorted({entry["team"] for entries in players.values() for entry in entries or []})
    if player_teams:
        st.markdown("**Player advanced stats**")
        for tab, team in zip(st.tabs(player_teams), player_teams):
            with tab:
                for section, columns in PLAYER_SECTIONS:
                    rows = [
                        {"Player": entry.get("player"), **{label: pick(entry, *path) for label, *path in columns}}
                        for entry in players.get(section) or [] if entry.get("team") == team
                    ]
                    if rows:
                        st.markdown(readable(section))
                        st.dataframe(pd.DataFrame(rows).round(3), width="stretch", hide_index=True)


@st.dialog("Box score", width="large")
def show_box_scores(team: pd.Series, week: str, season: int) -> None:
    st.subheader(f"{team['city']} {team['name']} | {week}")
    if week == "Preseason":
        st.info("No games have been played yet in the preseason.")
        return
    if not any(BOXSCORE_DIRECTORY.glob("*.json")):
        st.info("No new box scores have been added. Run `python boxscore.py` first.")
        return
    box_scores = team_box_scores(team["city"], week, season)
    if not box_scores:
        st.info(f"No box score for {team['city']} in {week}. This was a bye week or the game hasn't not been played yet.")
        return
    for index, box_score in enumerate(box_scores):
        if index:
            st.divider()
        render_box_score(box_score)


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
    highlighted_team: int | None = None,
) -> tuple[Figure, list[tuple[pd.Timestamp, float, float]]]:
    history = history.copy()
    history["snapshot_date"] = pd.to_datetime(history["snapshot_date"])
    fig, axis = plt.subplots(figsize=(8, 5), dpi=140)
    axis.set_facecolor("#FAFAFC")
    fig.patch.set_facecolor("#FAFAFC")
    for team_id, team_history in history.groupby("team_id", sort=False):
        team_history = team_history.sort_values("snapshot_date")
        abbreviation = team_history["abbreviation"].iloc[0]
        primary, secondary, *tertiary = TEAM_COLORS[abbreviation]
        dates, ranks = team_history["snapshot_date"], team_history["rank"]
        endpoint = (dates.iloc[-1], ranks.iloc[-1])
        dimmed = highlighted_team is not None and team_id != highlighted_team
        if dimmed:
            axis.plot(dates, ranks, color=NEUTRAL_LINE_COLOR, linewidth=1.6, zorder=1)
            axis.scatter(*endpoint, s=60, color=NEUTRAL_LINE_COLOR, zorder=1)
        else:
            emphasis = 1.6 if team_id == highlighted_team else 1
            layer = 6 if team_id == highlighted_team else 2
            axis.plot(dates, ranks, color=secondary, linewidth=4 * emphasis,
                      alpha=0.9, zorder=layer)
            axis.plot(dates, ranks, color=primary, linewidth=2.2 * emphasis, zorder=layer + 1)
            axis.scatter(
                *endpoint, s=95, color=secondary,
                edgecolors=tertiary[0] if tertiary else primary, linewidths=2, zorder=layer + 2,
            )
        if team_id == highlighted_team:
            axis.scatter(dates, ranks, s=40, color=primary, edgecolors=secondary,
                         linewidths=1.5, zorder=layer + 2)
            for date, rank in zip(dates, ranks):
                axis.annotate(str(rank), (date, rank), xytext=(0, 8),
                              textcoords="offset points", ha="center", fontsize=8,
                              weight="bold", color=primary, zorder=layer + 3)
        logo = plt.imread(IMAGE_DIRECTORY / TEAM_LOGOS[abbreviation])
        axis.add_artist(AnnotationBbox(
            OffsetImage(logo, zoom=0.035, alpha=0.35 if dimmed else 1), endpoint,
            xybox=(16, 0), xycoords="data", boxcoords="offset points",
            frameon=False, pad=0,
        ))
    team_count = history["team_id"].nunique()
    last_date = timeline_end if timeline_end is not None else history["snapshot_date"].max()
    axis.set_xlim(history["snapshot_date"].min(), last_date + pd.Timedelta(days=3))
    axis.set_ylim(team_count + 0.7, 0.3)
    axis.set_yticks(range(1, team_count + 1))
    axis.set_ylabel("ACC Rank (1 = first)")
    axis.set_xlabel("Week / Snapshot Date")
    axis.set_title(f"{season} Standings Bump Chart", loc="left", weight="bold", pad=16)
    snapshot_dates = sorted(history["snapshot_date"].unique())
    axis.set_xticks(
        mdates.date2num(snapshot_dates),
        [f"{season_period_for_date(pd.Timestamp(date), season)}\n{pd.Timestamp(date):%b %d}"
         for date in snapshot_dates],
        fontsize=8,
    )
    axis.grid(axis="both", color="#D8D8E0", linewidth=0.8)
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    highlighted_points = []
    highlighted_history = history[history["team_id"] == highlighted_team].sort_values("snapshot_date")
    for date, rank in zip(highlighted_history["snapshot_date"], highlighted_history["rank"]):
        x, y = axis.transData.transform((mdates.date2num(date), rank))
        highlighted_points.append((date, x, fig.bbox.height - y))
    return fig, highlighted_points


def render_animation(snapshot_history: pd.DataFrame, season: int) -> None:
    st.subheader("ACC Standings Bump Chart")
    if snapshot_history.empty:
        st.info(f"No ACC standings history found for the {season} season yet.")
        return
    history = prepare_animation_history(
        snapshot_history, season, pd.Timestamp.today().normalize(),
    )
    if history.empty:
        st.info("No snapshots from completed football weeks are available yet.")
        return
    animation_dates = sorted(history["snapshot_date"].unique())
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
    team_names = (
        history.drop_duplicates("team_id")
        .assign(full_name=lambda teams: teams["city"] + " " + teams["name"])
        .sort_values("full_name")
        .set_index("team_id")["full_name"]
    )
    st.selectbox(
        "Highlight a team", [None, *team_names.index], key="highlighted_team",
        format_func=lambda team_id: "All teams" if team_id is None else team_names[team_id],
    )

    @st.fragment(run_every="1s" if st.session_state.animation_playing else None)
    def show_standings_animation() -> None:
        frame_index = st.session_state.animation_index
        snapshot_date = pd.Timestamp(animation_dates[frame_index])
        week = season_period_for_date(snapshot_date, season)
        st.caption(f"Snapshot: {snapshot_date:%b %d, %Y}  \n{week}")
        highlighted_team = st.session_state.highlighted_team
        chart, points = standings_chart(
            history[history["snapshot_date"] <= snapshot_date], season,
            timeline_end=pd.Timestamp(animation_dates[-1]),
            highlighted_team=highlighted_team,
        )
        chart_size = chart.bbox.width, chart.bbox.height
        image = chart_image(chart)
        if highlighted_team is None or st.session_state.animation_playing:
            st.image(image, width="stretch")
        else:
            click = streamlit_image_coordinates(
                Image.open(BytesIO(image)), key="season_chart_click",
                width="stretch", cursor="pointer",
            )
            st.caption("Click a dot on the highlighted line to see that week's box score.")
            if click and click["unix_time"] != st.session_state.get("last_chart_click"):
                st.session_state.last_chart_click = click["unix_time"]
                x = click["x"] * chart_size[0] / click["width"]
                y = click["y"] * chart_size[1] / click["height"]
                distance, index = min(
                    ((x - point_x) ** 2 + (y - point_y) ** 2, index)
                    for index, (_, point_x, point_y) in enumerate(points)
                )
                if distance <= DOT_CLICK_RADIUS ** 2:
                    show_box_scores(
                        history[history["team_id"] == highlighted_team].iloc[0],
                        season_period_for_date(points[index][0], season), season,
                    )
        if st.session_state.animation_playing:
            if frame_index < len(animation_dates) - 1:
                st.session_state.animation_index = frame_index + 1
            else:
                st.session_state.animation_playing = False
                st.rerun()

    show_standings_animation()


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
    st.subheader("Win/Loss Horizontal Bar Chart")
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


def _answer_after_prior_turns(
    question: str,
    previous_turns: list[dict],
    dashboard_context: str,
) -> str:
	history = []
	for turn in previous_turns:
		history.append({"role": "user", "content": turn["question"]})
		try:
			answer = turn["future"].result()
		except Exception:
			answer = "No response was available for this earlier question."
		history.append({"role": "assistant", "content": answer})
	return chat.answer_question(question, history, dashboard_context)


@st.fragment(run_every="1s")
def render_chat(dashboard_context: str) -> None:
    st.subheader("AI Chatbox")
    if "chat_turns" not in st.session_state:
        turns = []
        legacy_messages = st.session_state.pop("chat_messages", [])
        for message in legacy_messages:
            if message.get("role") == "user":
                future = Future()
                turns.append({"question": message["content"], "future": future})
            elif message.get("role") == "assistant" and turns:
                future = turns[-1]["future"]
                if not future.done():
                    future.set_result(message["content"])
        for turn in turns:
            if not turn["future"].done():
                turn["future"].set_result(
                    "No response was available for this earlier question."
                )
        st.session_state.chat_turns = turns

    turns = st.session_state.chat_turns
    for turn in turns:
        with st.chat_message("user"):
            st.markdown(turn["question"])

        future = turn["future"]
        if future.done() and "answer" not in turn and "error" not in turn:
            try:
                turn["answer"] = future.result()
            except Exception as error:
                turn["error"] = str(error)

        with st.chat_message("assistant"):
            if "error" in turn:
                st.error(turn["error"])
            elif "answer" in turn:
                st.markdown(turn["answer"])
            elif future.running():
                st.caption("Working on this question. Any rate-limit wait will be retried automatically.")
            else:
                st.caption("Queued behind an earlier question.")

    question = st.chat_input("Ask any question about the ACC standings this season")
    if not question:
        return

    previous_turns = turns.copy()
    future = CHAT_EXECUTOR.submit(
        _answer_after_prior_turns,
        question,
        previous_turns,
        dashboard_context,
    )
    turns.append({"question": question, "future": future})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        st.caption("Question accepted. Waiting for the chat model...")


def render_saved_summary() -> None:
    st.subheader("AI Generated Summary")
    if not SUMMARY_PATH.is_file():
        st.info("No generated summary is available yet.")
        return

    summary = SUMMARY_PATH.read_text(encoding="utf-8").splitlines()
    if summary and summary[0].startswith("# "):
        summary = summary[1:]
    st.markdown("\n".join(summary))


def main() -> None:
    st.set_page_config(page_title="2026 NCAAF ACC Standings Dashboard", layout="wide")
    st.markdown(
        "<style>.block-container {padding-top: 1rem; padding-bottom: 1rem;}</style>",
        unsafe_allow_html=True,
    )
    st.title("2026 NCAA College Football ACC Standings Dashboard")

    with st.spinner("Building database from the latest snapshot..."):
        build_db.main()

    season = 2026
    standings = analyze.get_conference_standings(season)

    if standings.empty:
        st.info(f"No ACC standings found for the {season} season yet.")
        return

    history = analyze.get_standings_history(season)
    history = history.sort_values(
        ["snapshot_date", "wins", "losses", "city"],
        ascending=[True, False, True, True],
    ).reset_index(drop=True)
    history["rank"] = history.groupby("snapshot_date").cumcount() + 1
    games_played = (history["wins"] + history["losses"]).groupby(history["snapshot_date"])
    history.loc[games_played.transform("sum") == 0, "rank"] = history["team_id"].nunique()

    chat_history = history.assign(week=[
        season_period_for_date(pd.Timestamp(date), season)
        for date in history["snapshot_date"]
    ])

    metric = render_standings(standings, display=False) if hasattr(render_standings, 'display') else None
    
    dashboard_context = chat.build_dashboard_context(standings, chat_history, metric)
    render_chat(dashboard_context)
    render_saved_summary()

    standings_column, animation_column = st.columns(2, gap="large")
    with standings_column, st.container(border=True):
        # We assume render_standings actually draws the chart here
        metric = render_standings(standings) 
    with animation_column, st.container(border=True):
        render_animation(history, season)

    render_raw_standings(history, metric)

    st.divider()
    st.markdown("#### Data Sources")
    st.markdown(
        """
        <div style="display: flex; gap: 40px; align-items: center; padding-bottom: 20px;">
            <div>
                <p style="margin-bottom: 5px; font-size: 14px; color: gray;">Standings data provided by:</p>
                <a href="https://www.balldontlie.io/" target="_blank">
                    <img src="https://www.balldontlie.io/public/logo-full.svg" alt="balldontlie" width="150">
                </a>
            </div>
            <div>
                <p style="margin-bottom: 5px; font-size: 14px; color: gray;">Boxscore data provided by:</p>
                <a href="https://collegefootballdata.com/" target="_blank">
                    <img src="https://collegefootballdata.com/brand/cfbd-watermark-dark.png" alt="CollegeFootballData" width="150">
                </a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
