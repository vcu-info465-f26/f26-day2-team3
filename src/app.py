import pandas as pd
import streamlit as st

import analyze
import build_db


@st.cache_resource
def initialize_database() -> None:
	build_db.main()


@st.cache_data
def load_standings_history(season: int) -> pd.DataFrame:
	return analyze.get_standings_history(season)


def main() -> None:
	st.set_page_config(page_title="ACC Standings", layout="wide")
	st.title("ACC Standings")
	st.caption("Conference records across daily snapshots")

	initialize_database()
	history = load_standings_history(2026)
	if history.empty:
		st.info("No ACC standings snapshots are available for the 2026 season.")
		return

	latest_date = history["snapshot_date"].max()
	standings = history[history["snapshot_date"] == latest_date].reset_index(drop=True)
	team_names = standings["city"] + " " + standings["name"]

	selected_team = st.selectbox("Team trend", team_names.tolist())
	selected_metric = st.selectbox("Trend metric", ["wins", "losses"])
	history_team_names = history["city"] + " " + history["name"]
	team_history = history[history_team_names == selected_team].set_index("snapshot_date")

	left_chart, right_chart = st.columns(2)
	with left_chart:
		st.subheader(f"{selected_team}: {selected_metric.title()} over time")
		st.line_chart(team_history[selected_metric])

	with right_chart:
		st.subheader("Calculated Win Percentage by Team")
		games_played = standings["wins"] + standings["losses"]
		win_percentage = (
			standings["wins"].div(games_played.where(games_played.ne(0))).fillna(0) * 100
		)
		percentage_chart = pd.DataFrame(
			{"Team": team_names, "Win percentage (%)": win_percentage}
		).sort_values("Win percentage (%)", ascending=False).set_index("Team")
		st.bar_chart(percentage_chart)

	st.subheader(f"Raw standings data - {latest_date}")
	st.dataframe(standings, hide_index=True)


if __name__ == "__main__":
	main()