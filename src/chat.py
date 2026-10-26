import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Lock

import pandas as pd
import requests
import streamlit as st


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"
API_MIN_INTERVAL_SECONDS = 60
MAX_RATE_LIMIT_RETRIES = 2

_api_request_lock = Lock()
_next_api_request_at = 0.0


SYSTEM_PROMPT = """You answer questions about the ACC standings dashboard.
Use only the dashboard context supplied in this message. Do not use outside
knowledge or treat a user's assumptions as facts. If the context does not
contain enough information to answer, say that the dashboard data does not
provide the answer. For numeric answers, state the relevant team, metric, and
snapshot date when available. Do not guess or extrapolate.

Historical data is compact: historical_teams maps team indexes to names,
and historical_wins_losses contains [snapshot_date, [[team_index, wins, losses], ...]] rows.

Dashboard context:
"""


def _records(frame: pd.DataFrame) -> list[dict]:
	if frame.empty:
		return []
	return json.loads(frame.to_json(orient="records", date_format="iso"))


def build_dashboard_context(
	standings: pd.DataFrame,
	history: pd.DataFrame,
	selected_metric: str,
) -> str:
	if standings.empty:
		return json.dumps({"summary": "No standings are currently displayed."})

	current = standings.copy()
	metric = selected_metric if selected_metric in {"wins", "losses"} else "wins"
	other_metric = "losses" if metric == "wins" else "wins"
	current = current.sort_values(
		[metric, other_metric, "city"],
		ascending=[False, True, True],
	)

	snapshot_date = str(standings["snapshot_date"].iloc[0])
	season = int(standings["season"].iloc[0])
	if not history.empty:
		dates = pd.to_datetime(history["snapshot_date"], errors="coerce").dropna()
		date_range = {
			"start": dates.min().date().isoformat(),
			"end": dates.max().date().isoformat(),
		}
		team_rows = (
			history[["abbreviation", "city"]]
			.drop_duplicates()
			.sort_values("abbreviation")
			.reset_index(drop=True)
		)
		team_ids = {
			row.abbreviation: index
			for index, row in enumerate(team_rows.itertuples(index=False))
		}
		historical_wins_losses = []
		for date, snapshot in history.groupby("snapshot_date", sort=True):
			rows = [
				[
					team_ids[row.abbreviation],
					None if pd.isna(row.wins) else int(row.wins),
					None if pd.isna(row.losses) else int(row.losses),
				]
				for row in snapshot[["abbreviation", "wins", "losses"]].itertuples(index=False)
			]
			historical_wins_losses.append([str(date), rows])
		historical_teams = [
			{"id": index, "abbreviation": row.abbreviation, "city": row.city}
			for index, row in enumerate(team_rows.itertuples(index=False))
		]
	else:
		date_range = {"start": snapshot_date, "end": snapshot_date}
		historical_teams = []
		historical_wins_losses = []

	leader = current.iloc[0]
	summary = (
		f"The {season} ACC standings show {len(standings)} teams in the latest "
		f"snapshot dated {snapshot_date}. Sorted by {metric}, "
		f"{leader['city']} leads with {int(leader[metric])} {metric}."
	)
	context = {
		"summary": summary,
		"season": season,
		"date_range_of_displayed_history": date_range,
		"latest_snapshot_date": snapshot_date,
		"chart_metric_selected": metric,
		"current_standings": _records(current),
		"historical_teams": historical_teams,
		"historical_wins_losses": historical_wins_losses,
	}
	return json.dumps(context, ensure_ascii=True, separators=(",", ":"))


def _api_key() -> str | None:
	key = os.getenv("GROQ_API_KEY")
	if key:
		return key
	try:
		return st.secrets.get("GROQ_API_KEY")
	except Exception:
		return None


def _retry_after_seconds(response: requests.Response) -> float:
	delays = []
	for header in (
		"Retry-After",
		"x-ratelimit-reset-tokens",
		"x-ratelimit-reset-requests",
	):
		value = response.headers.get(header)
		if not value:
			continue
		try:
			delays.append(float(value))
			continue
		except ValueError:
			pass

		match = re.fullmatch(
			r"(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?",
			value.strip(),
		)
		if match and any(match.groups()):
			delays.append(float(match.group(1) or 0) * 60 + float(match.group(2) or 0))
		elif header == "Retry-After":
			try:
				retry_at = parsedate_to_datetime(value)
				if retry_at.tzinfo is None:
					retry_at = retry_at.replace(tzinfo=timezone.utc)
				delays.append((retry_at - datetime.now(timezone.utc)).total_seconds())
			except (TypeError, ValueError, OverflowError):
				continue
	return max(API_MIN_INTERVAL_SECONDS, max(delays, default=0))


def _post_chat_completion(api_key: str, payload: dict) -> requests.Response:
	global _next_api_request_at
	with _api_request_lock:
		for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
			wait_seconds = _next_api_request_at - time.monotonic()
			if wait_seconds > 0:
				time.sleep(wait_seconds)

			response = requests.post(
				GROQ_CHAT_URL,
				headers={"Authorization": f"Bearer {api_key}"},
				json=payload,
				timeout=30,
			)
			request_finished_at = time.monotonic()
			if response.status_code != 429:
				_next_api_request_at = 0.0
				return response
			_next_api_request_at = max(
				_next_api_request_at,
				request_finished_at + _retry_after_seconds(response),
			)
			if attempt == MAX_RATE_LIMIT_RETRIES:
				try:
					provider_error = response.json().get("error", {})
					message = provider_error.get("message")
				except (AttributeError, ValueError):
					message = None
				if message and "tokens per minute" in message.lower():
					raise RuntimeError(
						"Groq still rejects this request after waiting. The prompt may "
						f"exceed the account's per-minute token limit: {message}"
					)
				raise RuntimeError(
					"Groq rate limiting persisted after waiting and retries. "
					f"{message or 'Try again after the provider limit resets.'}"
				)
	return response


def answer_question(
	question: str,
	history: list[dict[str, str]],
	dashboard_context: str,
) -> str:
	api_key = _api_key()
	if not api_key:
		raise RuntimeError("Chat is unavailable because GROQ_API_KEY is not configured.")

	messages = [{
		"role": "system",
		"content": SYSTEM_PROMPT + dashboard_context,
	}]
	messages.extend(
		{"role": message["role"], "content": message["content"]}
		for message in history
		if message.get("role") in {"user", "assistant"}
		and isinstance(message.get("content"), str)
	)
	messages.append({"role": "user", "content": question})

	response = _post_chat_completion(
		api_key,
		{
			"model": os.getenv("GROQ_MODEL", DEFAULT_MODEL),
			"messages": messages,
			"temperature": 0,
		},
	)
	response.raise_for_status()
	return response.json()["choices"][0]["message"]["content"].strip()
