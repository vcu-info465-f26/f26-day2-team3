import matplotlib.pyplot as plt
import pandas as pd


def top_10_acc_chart(history: pd.DataFrame) -> None:
	history = history.copy()
	history["snapshot_date"] = pd.to_datetime(history["snapshot_date"])
	latest_date = history["snapshot_date"].max()
	latest_standings = history[history["snapshot_date"] == latest_date].copy()
	latest_standings = latest_standings.dropna(subset=["wins", "losses"])
	latest_standings = latest_standings.sort_values(
		["win_percentage", "wins", "losses"],
		ascending=[False, False, True],
	).head(10)

	if latest_standings.empty:
		return

	figure, axis = plt.subplots(figsize=(12, 6))
	positions = list(range(len(latest_standings)))
	axis.bar(positions, latest_standings["wins"], color="#167d75", label="Wins")
	axis.bar(positions, latest_standings["losses"], color="#d9e4e3", label="Losses")
	axis.set_xticks(positions)
	axis.set_xticklabels(latest_standings["team"], rotation=45, ha="right")
	axis.set_title(f"Top 10 ACC teams on {latest_date.strftime('%b %d, %Y')}")
	axis.set_xlabel("Team")
	axis.set_ylabel("Record")
	axis.legend()

	for index, (wins, losses) in enumerate(zip(latest_standings["wins"], latest_standings["losses"])):
		label = f"{wins}-{losses}"
		axis.text(index, max(wins, losses) + 0.5, label, ha="center", va="bottom", fontsize=8)

	axis.set_ylim(0, max(latest_standings["wins"].max(), latest_standings["losses"].max()) * 1.5)
	plt.tight_layout()
	plt.show()


# Example usage:
# history = analyze.get_standings_history()
# top_10_acc_chart(history)