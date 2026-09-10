# Runs on a GitHub Actions schedule.
# Fetches live NCAAF data from the balldontlie endpoints (conferences, teams, standings)
# Writes output to a dated snapshot (e.g., data/2026-09-10.json).
import requests

def get_teams():
    response = requests.get(
        'https://api.balldontlie.io/ncaaf/v1/teams',
        headers={'Authorization': 'BALLDONTLIE_API_KEY'}
    )
    data = response.json()
    print(data)
    return data

get_teams()
 