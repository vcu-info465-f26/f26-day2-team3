from pathlib import Path
import sqlite3

import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from matplotlib.ticker import MaxNLocator
import pandas as pd
import streamlit as st

from analyze import get_standings_history


ROOT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = ROOT_DIR / "data" / "bdl.db"
LOGO_DIR = ROOT_DIR / "img"

TEAM_STYLES = {
	"Boston College": ("#8A100B", "#BC9B6A", "Boston_College_Eagles.png"),
	"California": ("#003262", "#FDB515", "California_Golden_Bears.png"),
	"Clemson": ("#F56600", "#522D80", "Clemson_Tigers.png"),
	"Duke": ("#00539B", "#FFFFFF", "Duke_Blue_Devils.png"),
	"Florida State": ("#782F40", "#CEB888", "Florida_State_Seminoles.png"),
	"Georgia Tech": ("#B3A369", "#003057", "Georgia_Tech_Yellow_Jackets.png"),
	"Louisville": ("#AD0000", "#000000", "Louisville_Cardinals.png"),
	"Miami": ("#F47321", "#005030", "Miami_Hurricanes.png"),
	"North Carolina": ("#7BAFD4", "#13294B", "North_Carolina_Tar_Heels.png"),
	"NC State": ("#CC0000", "#000000", "NC_State_Wolfpack.png"),
	"Pittsburgh": ("#003594", "#FFB81C", "Pittsburgh_Panthers.png"),
	"SMU": ("#CC0035", "#354CA1", "SMU_Mustangs.png"),
	"Stanford": ("#8C1515", "#FFFFFF", "Stanford_Cardinal.png"),
	"Syracuse": ("#F76900", "#000E54", "Syracuse_Orange.png"),
	"Virginia": ("#E57200", "#232D4B", "Virginia_Cavaliers.png"),
	"Virginia Tech": ("#861F41", "#E5751F", "Virginia_Tech_Hokies.png"),
	"Wake Forest": ("#9E7E38", "#000000", "Wake_Forest_Demon_Deacons.png"),
}


@st.cache_data
def load_latest_acc_standings(database_path: str) -> pd.DataFrame:
	with sqlite3.connect(f"file:{database_path}?mode=ro", uri=True) as connection:
		return pd.read_sql_query(
			"""
			WITH latest AS (
				SELECT season, MAX(snapshot_date) AS snapshot_date
				FROM standings
				WHERE conference_id = 1
				GROUP BY season
				ORDER BY season DESC
				LIMIT 1
			)
			SELECT teams.city AS team, standings.wins, standings.losses,
			       standings.season, standings.snapshot_date
			FROM standings
			JOIN teams ON teams.id = standings.team_id
			JOIN latest ON latest.season = standings.season
			            AND latest.snapshot_date = standings.snapshot_date
			WHERE standings.conference_id = 1
			ORDER BY teams.city
			""",
			connection,
		)


@st.cache_data
def load_acc_history(season: int) -> pd.DataFrame:
	return get_standings_history(season)


def make_standings_chart(standings: pd.DataFrame, metric: str) -> plt.Figure:
	other_metric = "losses" if metric == "wins" else "wins"
	standings = standings.sort_values(
		[metric, other_metric, "team"],
		ascending=[False, True, True],
	).reset_index(drop=True)

	fig, axis = plt.subplots(figsize=(12, max(7.2, len(standings) * 0.52)), dpi=140)
	fig.patch.set_facecolor("white")
	axis.set_facecolor("white")

	for position, row in standings.iterrows():
		primary, secondary, logo_name = TEAM_STYLES[row["team"]]
		value = int(row[metric])
		axis.barh(
			position,
			value,
			color=primary,
			edgecolor=secondary,
			linewidth=2,
			height=0.62,
			zorder=2,
		)
		logo_path = LOGO_DIR / logo_name
		if logo_path.exists():
			logo = plt.imread(logo_path)
			image = OffsetImage(logo, zoom=0.05)
			axis.add_artist(
				AnnotationBbox(
					image,
					(max(value - 0.25, 0.18), position),
					frameon=True,
					pad=0.08,
					bboxprops={"facecolor": "white", "edgecolor": secondary, "linewidth": 1.2},
					zorder=3,
				)
			)
		axis.text(value + 0.45, position, str(value), va="center", ha="left", color="#242424", fontsize=10)

	axis.set_yticks(range(len(standings)), standings["team"], fontsize=10)
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
	fig.subplots_adjust(left=0.19, right=0.96, top=0.94, bottom=0.035)
	return fig


st.set_page_config(page_title="ACC Standings", layout="wide")
st.markdown(
	"""
	<style>
		.block-container { max-width: 1180px; padding-top: 2.2rem; }
		[data-testid="stSelectbox"] label { color: #626262; font-size: 0.82rem; }
		h1 { color: #181818; font-size: 2rem; }
	</style>
	""",
	unsafe_allow_html=True,
)

st.title("ACC standings")
standings = load_latest_acc_standings(str(DATABASE_PATH))

if standings.empty:
	st.warning("No ACC standings are available in data/bdl.db.")
else:
	season = int(standings["season"].iloc[0])
	snapshot_date = standings["snapshot_date"].iloc[0]
	history = load_acc_history(season)
	control, context = st.columns([1, 3], vertical_alignment="bottom")
	with control:
		selection = st.selectbox("Sort teams by", ["Wins", "Losses"])
	with context:
		st.caption(f"{season} season · Latest update {snapshot_date} · {len(standings)} teams")

	chart = make_standings_chart(standings, selection.lower())
	st.pyplot(chart, width="stretch")
	plt.close(chart)

	history_table = history.sort_values(
		["snapshot_date", selection.lower(), "city"],
		ascending=[False, False, True],
	)
	st.subheader("Raw standings data")
	st.dataframe(history_table, width="stretch", hide_index=True)