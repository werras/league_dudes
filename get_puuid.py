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
    print(f"DEBUG: Requesting PUUID for {name}#{tag} from {url}")
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        puuid = response.json().get("puuid")
        print(f"DEBUG: Found PUUID: {puuid}")
        return puuid
    print(
        f"DEBUG: Failed to get PUUID. Status: {response.status_code} Body: {response.text}"
    )
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
        else:
            print(f"DEBUG: Skipping {name}#{tag} due to missing PUUID.")

    with open("friends_puuids.json", "w") as f:
        json.dump(puuid_results, f, indent=4)

    print("\nSuccess! PUUIDs mapped and saved.")


if __name__ == "__main__":
    main()
