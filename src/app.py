import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd
import streamlit as st

import analyze
import build_db


@st.cache_resource
def initialize_database() -> None:
	build_db.main()


st.set_page_config(page_title="ACC Standings Trends", layout="wide")
initialize_database()

st.title("ACC Standings Trends")
st.subheader("Win percentage over time")

history = analyze.get_standings_history()
if history.empty:
	st.info("No dated standings snapshots are available yet.")
else:
	team_options = sorted(history["team"].dropna().unique())
	selected_team = st.selectbox("Team", team_options)
	team_history = history[history["team"] == selected_team].copy()
	team_history["snapshot_date"] = pd.to_datetime(team_history["snapshot_date"])
	team_history = team_history.sort_values("snapshot_date")
	team_history = team_history.dropna(subset=["win_percentage"])

	if team_history.empty:
		st.info("No win-percentage data is available for this team.")
	else:
		figure, axis = plt.subplots(figsize=(10, 4.5))
		axis.plot(
			team_history["snapshot_date"],
			team_history["win_percentage"],
			marker="o",
			linewidth=2,
			color="#167d75",
		)
		axis.set_title(f"{selected_team} win percentage")
		axis.set_xlabel("Snapshot date")
		axis.set_ylabel("Win percentage")
		axis.set_ylim(0, 1)
		axis.yaxis.set_major_formatter(PercentFormatter(1))
		axis.xaxis.set_major_formatter(mdates.DateFormatter("%b %d, %Y"))
		axis.grid(axis="y", linestyle="--", alpha=0.35)
		axis.spines[["top", "right"]].set_visible(False)
		figure.autofmt_xdate()
		st.pyplot(figure, width="stretch")
		plt.close(figure)

	st.caption(
		"Track a team's win percentage across saved snapshots to see whether its "
		"current standing is part of a trend or a recent change."
	)