import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Lock

import openai
import pandas as pd
import requests
import streamlit as st


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"
API_MIN_INTERVAL_SECONDS = 2
MAX_RATE_LIMIT_RETRIES = 2
MAX_HISTORY_MESSAGES = 6

_api_request_lock = Lock()
_next_api_request_at = 0.0


SYSTEM_PROMPT = """You answer questions about the ACC standings dashboard.
Use only the dashboard context supplied in this message. Do not use outside
knowledge or treat a user's assumptions as facts. If the context does not
contain enough information to answer, say that the dashboard data does not
provide the answer. For numeric answers, state the relevant team, metric, and
snapshot date when available. Do not guess or extrapolate.

weekly_standings lists each football week with its final snapshot_date and the
ACC standings already ranked as "rank. Team wins-losses". Rank 1 is first place
and the highest rank number is last place. Read ranks directly from the list for
the week the user asks about; never use a different week's snapshot. If teams
share the same record, mention that they are tied. If a requested week is not
listed, say the dashboard has no data for that week. Keep answers short.

Dashboard context:
"""


def build_dashboard_context(
	standings: pd.DataFrame,
	history: pd.DataFrame,
	selected_metric: str,
) -> str:
	if standings.empty:
		return json.dumps({"summary": "No standings are currently displayed."})

	metric = selected_metric if selected_metric in {"wins", "losses"} else "wins"
	snapshot_date = str(standings["snapshot_date"].iloc[0])
	season = int(standings["season"].iloc[0])

	weekly_standings = []
	if not history.empty:
		final_dates = history.groupby("week", sort=False)["snapshot_date"].max()
		for week, date in sorted(final_dates.items(), key=lambda item: item[1]):
			snapshot = history[history["snapshot_date"] == date].sort_values(
				["wins", "losses", "city"], ascending=[False, True, True],
			)
			weekly_standings.append({
				"week": week,
				"snapshot_date": str(date),
				"standings": [
					f"{rank}. {row.city} {row.name} {int(row.wins)}-{int(row.losses)}"
					for rank, row in enumerate(snapshot.itertuples(index=False), start=1)
				],
			})

	context = {
		"season": season,
		"latest_snapshot_date": snapshot_date,
		"chart_metric_selected": metric,
		"weekly_standings": weekly_standings,
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
		for message in history[-MAX_HISTORY_MESSAGES:]
		if message.get("role") in {"user", "assistant"}
		and isinstance(message.get("content"), str)
	)
	messages.append({"role": "user", "content": question})

	model = os.getenv("GROQ_MODEL", DEFAULT_MODEL)
	payload = {"model": model, "messages": messages, "temperature": 0}
	if model.startswith("openai/gpt-oss"):
		payload["reasoning_effort"] = "low"
	response = _post_chat_completion(api_key, payload)
	response.raise_for_status()
	return response.json()["choices"][0]["message"]["content"].strip()
