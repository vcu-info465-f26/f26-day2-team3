import argparse
import json
import logging
import os
import re
import tempfile
import tomllib
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
SUMMARY_PATH = DATA_DIR / "summary.md"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"
ACC_ID = 1
REQUEST_TIMEOUT = 60
NUMBER_WORD = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
    r"eighteen|nineteen|twenty|first|second|third|fourth|fifth|"
    r"sixth|seventh|eighth|ninth|tenth)\b",
    re.IGNORECASE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def load_standings_history(data_dir: Path, season: int) -> list[dict]:
    history = []
    for snapshot_path in sorted(data_dir.glob("????-??-??.json")):
        snapshot_date = date.fromisoformat(snapshot_path.stem)
        if snapshot_date.year != season:
            continue

        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot_standings = []
        for record in payload.get("standings", []):
            if record.get("season", snapshot_date.year) != season:
                continue

            team = record.get("team")
            if not isinstance(team, dict):
                raise ValueError(f"Missing team details in {snapshot_path}")
            conference = team.get("conference")
            if isinstance(conference, dict):
                conference = conference.get("id")
            if conference != ACC_ID:
                continue

            wins = record.get("wins")
            losses = record.get("losses")
            team_id = team.get("id")
            team_name = team.get("full_name")
            city = team.get("college")
            if (
                type(team_id) is not int
                or type(wins) is not int
                or type(losses) is not int
                or not isinstance(team_name, str)
                or not team_name.strip()
                or not isinstance(city, str)
                or not city.strip()
            ):
                raise ValueError(f"Invalid ACC standings record in {snapshot_path}")

            snapshot_standings.append(
                {
                    "team_id": team_id,
                    "team_name": team_name,
                    "city": city.casefold(),
                    "wins": wins,
                    "losses": losses,
                }
            )

        if snapshot_standings:
            team_ids = [team["team_id"] for team in snapshot_standings]
            if len(team_ids) != len(set(team_ids)):
                raise ValueError(f"Duplicate ACC team in {snapshot_path}")
            snapshot_standings.sort(
                key=lambda team: (-team["wins"], team["losses"], team["city"])
            )
            history.append(
                {"date": snapshot_path.stem, "standings": snapshot_standings}
            )

    if not history:
        raise ValueError(f"No ACC standings snapshots found for the {season} season")
    return history


def generate_ai_overview(standings: list[dict]) -> str:
    load_dotenv(ROOT_DIR / ".env")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        secrets_path = ROOT_DIR / ".streamlit" / "secrets.toml"
        if secrets_path.is_file():
            with secrets_path.open("rb") as secrets_file:
                api_key = tomllib.load(secrets_file).get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. For local runs, set it in your environment "
            "or in the repository-root .env file or .streamlit/secrets.toml. "
            "For GitHub Actions, add it as a repository or environment secret."
        )

    facts = "\n".join(
        f"- {team['team_name']}: {team['wins']} wins, {team['losses']} losses"
        for team in standings
    )
    response = requests.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Write a brief, neutral paragraph about the competitive "
                        "picture in these ACC standings. Use only the supplied "
                        "teams and facts. Do not include digits, number words, "
                        "records, dates, or claims about unprovided events or "
                        "trends. Return only the paragraph."
                    ),
                },
                {"role": "user", "content": facts},
            ],
            "reasoning_effort": "low",
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    overview = response.json()["choices"][0]["message"]["content"]
    if not isinstance(overview, str) or not overview.strip():
        raise ValueError("The AI model returned an empty standings overview")
    overview = overview.strip()
    if re.search(r"\d", overview) or NUMBER_WORD.search(overview):
        raise ValueError("The AI overview included a number; refusing inaccurate output")
    return overview


def render_summary(history: list[dict], overview: str) -> str:
    latest = history[-1]
    leaders = latest["standings"][:3]
    lines = [
        "# ACC Football Standings Summary",
        "",
        (
            f"**Standings data range:** {history[0]['date']} to {latest['date']} "
            f"({len(history)} snapshots)"
        ),
        f"**Latest dashboard snapshot:** {latest['date']}",
        "",
        "## Standings leaders",
        "",
        "| Rank | Team | Overall record | Wins | Losses |",
        "| ---: | --- | ---: | ---: | ---: |",
    ]
    for rank, team in enumerate(leaders, start=1):
        lines.append(
            f"| {rank} | {team['team_name']} | "
            f"{team['wins']}-{team['losses']} | {team['wins']} | {team['losses']} |"
        )
    lines.extend(
        [
            "",
            "## AI-generated overview",
            "",
            overview,
            "",
        ]
    )
    return "\n".join(lines)


def write_summary_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Summarize ACC football standings")
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args(argv)

    history = load_standings_history(DATA_DIR, args.season)
    overview = generate_ai_overview(history[-1]["standings"])
    summary = render_summary(history, overview)
    write_summary_atomically(SUMMARY_PATH, summary)
    logger.info("Generated ACC standings summary at %s", SUMMARY_PATH)


if __name__ == "__main__":
    main()
