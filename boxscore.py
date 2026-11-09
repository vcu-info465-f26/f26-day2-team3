import argparse
import json
import logging
import os
import time
from pathlib import Path

import cfbd
import urllib3
from cfbd.exceptions import ApiException, NotFoundException
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
BOXSCORE_DIR = ROOT_DIR / "boxscore"
CONFERENCE = "ACC"
REQUEST_TIMEOUT_SECONDS = 30
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = 2
MAX_BACKOFF_SECONDS = 120
PAUSE_BETWEEN_REQUESTS_SECONDS = 1
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
GAME_IDS_BY_WEEK = {
    1: [401856766, 401858204, 401858207, 401858211, 401858202, 401856776, 401856777, 401858210,
        401864570, 401858206, 401858209, 401856661, 401858201, 401858208, 401856660, 401858212],
    2: [401858213, 401858214, 401858216, 401856681, 401858215, 401858224, 401856790, 401858219,
        401858222, 401858218, 401858217, 401858220, 401858221, 401858223],
    3: [401858225, 401856695, 401858233, 401858226, 401858227, 401858231, 401858228, 401856685,
        401858232, 401858229, 401858230, 401856802],
    4: [401858234, 401858237, 401864572, 401858242, 401858244, 401858241, 401858236, 401858239,
        401858240, 401858243, 401858238],
    5: [401858245, 401858252, 401858249, 401858250, 401858247, 401858251, 401858248, 401858246,
        401858253],
    6: [401858254, 401858259, 401858256, 401858255, 401858260, 401858258, 401858257],
    7: [401858268, 401858266, 401858269, 401858261, 401858263, 401858267, 401858262, 401858264,
        401858265],
    8: [401858271, 401858273, 401858272, 401858276, 401858270, 401858275, 401858274],
    9: [401858279, 401858284, 401858277, 401858280, 401858278, 401858281, 401858283, 401858282],

    10: [
        401858288,
        401858285,
        401858289,
        401858292,
        401858286,
        401858290,
        401858291,
        401858287
    ],
    11: [
        # Fri Nov 13: Florida State @ Pittsburgh
        # Sat Nov 14: Louisville @ North Carolina
        # Sat Nov 14: Stanford @ Virginia Tech
        # Sat Nov 14: Duke @ Miami
        # Sat Nov 14: Wake Forest @ SMU
        # Sat Nov 14: Syracuse @ NC State
        # Sat Nov 14: Georgia Tech @ Clemson
        # Sat Nov 14: Boston College @ Notre Dame
        # Sat Nov 14: California @ Virginia
    ],
    12: [
        # Fri Nov 20: Clemson @ Duke
        # Sat Nov 21: Virginia Tech @ Miami
        # Sat Nov 21: Wake Forest @ Georgia Tech
        # Sat Nov 21: NC State @ Florida State
        # Sat Nov 21: North Carolina @ Virginia
        # Sat Nov 21: Pittsburgh @ Louisville
        # Sat Nov 21: Stanford @ California
        # Sat Nov 21: Syracuse @ Boston College
        # Sat Nov 21: SMU @ Notre Dame
    ],
    13: [
        # Fri Nov 27: Florida @ Florida State
        # Sat Nov 28: Boston College @ Miami
        # Sat Nov 28: Georgia Tech @ Georgia
        # Sat Nov 28: Notre Dame @ Syracuse
        # Sat Nov 28: Louisville @ Kentucky
        # Sat Nov 28: Duke @ Wake Forest
        # Sat Nov 28: South Carolina @ Clemson
        # Sat Nov 28: NC State @ North Carolina
        # Sat Nov 28: Pittsburgh @ California
        # Sat Nov 28: SMU @ Stanford
        # Sat Nov 28: Virginia @ Virginia Tech
    ],
    14: [
        # Placeholder 
    ],
    15: [
        # Placeholder 
    ],
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def retry_after_seconds(error: ApiException) -> float | None:
    value = (error.headers or {}).get("Retry-After")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def call_with_retry(request, *args, **kwargs):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = request(*args, _request_timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
            time.sleep(PAUSE_BETWEEN_REQUESTS_SECONDS)
            return result
        except NotFoundException:
            raise
        except ApiException as error:
            if error.status not in RETRYABLE_STATUSES or attempt == MAX_ATTEMPTS:
                raise
            reason = f"HTTP {error.status}"
            wait = retry_after_seconds(error)
        except urllib3.exceptions.HTTPError as error:
            if attempt == MAX_ATTEMPTS:
                raise
            reason = type(error).__name__
            wait = None
        wait = min(wait or BACKOFF_SECONDS * 2 ** (attempt - 1), MAX_BACKOFF_SECONDS)
        logger.warning("%s on %s (attempt %d/%d); retrying in %.0fs",
                       reason, request.__name__, attempt, MAX_ATTEMPTS, wait)
        time.sleep(wait)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Download ACC box scores from the CFBD API")
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args(argv)
    game_ids = [game_id for week_ids in GAME_IDS_BY_WEEK.values() for game_id in week_ids]

    BOXSCORE_DIR.mkdir(exist_ok=True)
    missing_ids = [game_id for game_id in game_ids if not (BOXSCORE_DIR / f"{game_id}.json").exists()]
    logger.info("%d of %d box scores already downloaded", len(game_ids) - len(missing_ids), len(game_ids))
    if not missing_ids:
        return

    load_dotenv(ROOT_DIR / ".env")
    api_key = os.getenv("CFBD_API_KEY")
    if not api_key:
        raise SystemExit("CFBD_API_KEY is missing. Set it in your environment or the repository-root .env file.")

    saved = skipped = 0
    with cfbd.ApiClient(cfbd.Configuration(access_token=api_key)) as api_client:
        games_api = cfbd.GamesApi(api_client)
        season_games = {
            game.id: game for game in call_with_retry(
                games_api.get_games,
                year=args.season, season_type=cfbd.SeasonType.BOTH, conference=CONFERENCE,
            )
        }
        for game_id in missing_ids:
            game = season_games.get(game_id) or next(
                iter(call_with_retry(games_api.get_games, id=game_id)), None,
            )
            if game is None:
                logger.warning("Game %s was not found", game_id)
                skipped += 1
                continue
            try:
                advanced = call_with_retry(games_api.get_advanced_box_score, id=game_id)
            except NotFoundException:
                logger.warning("No advanced box score for %s at %s (game %s)",
                               game.away_team, game.home_team, game_id)
                skipped += 1
                continue
            payload = {"game": game.to_dict(), "advanced": advanced.to_dict()}
            (BOXSCORE_DIR / f"{game_id}.json").write_text(
                json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8",
            )
            saved += 1
    logger.info("Saved %d new box scores to %s (%d unavailable)", saved, BOXSCORE_DIR, skipped)


if __name__ == "__main__":
    main()