import os
import requests
from dotenv import load_dotenv

load_dotenv()


def get_conferences():
    url = "https://api.balldontlie.io/ncaaf/v1/conferences"

    api_key = os.getenv("BALLDONTLIE_API_KEY")

    headers = {
        "Authorization": api_key
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()

    print(data)

    return data["data"]


if __name__ == "__main__":
    conferences = get_conferences()

    for conference in conferences:
        print(
            conference["id"],
            conference["name"],
            conference["abbreviation"]
        )