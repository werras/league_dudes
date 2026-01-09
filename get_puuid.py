import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("RIOT_API_KEY")


def load_config():
    with open("friends_config.json", "r") as f:
        return json.load(f)


def get_puuid(name, tag, region):
    url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{name}/{tag}"
    headers = {"X-Riot-Token": API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json().get("puuid")
    return None


def main():
    config = load_config()
    region = config["settings"]["region"]
    puuid_results = {}

    for friend in config["friends"]:
        name, tag = friend["name"], friend["tag"]
        print(f"Syncing: {name}#{tag}...")

        puuid = get_puuid(name, tag, region)
        if puuid:
            puuid_results[f"{name}#{tag}"] = puuid

    with open("friends_puuids.json", "w") as f:
        json.dump(puuid_results, f, indent=4)

    print("\nSuccess! PUUIDs mapped and saved.")


if __name__ == "__main__":
    main()
