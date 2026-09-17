import os
import requests
from dotenv import load_dotenv

load_dotenv()


def get_standings(conference_id, season):
    url = "https://api.balldontlie.io/ncaaf/v1/standings"

    api_key = os.getenv("BALLDONTLIE_API_KEY")

    headers = {
        "Authorization": api_key
    }

    params = {
        "conference_id": conference_id,
        "season": season
    }

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()

    print(data.keys())
    print(data)

    return data["data"]


if __name__ == "__main__":
    standings = get_standings(1, 2026)

    for team in standings:
        print(
            team["team"]["full_name"],
            "Wins:", team["wins"],
            "Losses:", team["losses"]
        )