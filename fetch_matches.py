import json
import os
from decimal import Decimal

import boto3  # AWS SDK
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("RIOT_API_KEY")

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb", region_name="us-west-1")
table = dynamodb.Table("LeagueMatches")


## get config details
def load_config():
    with open("friends_config.json", "r") as f:
        return json.load(f)


## need puuids; use gamer tags in config file to acquire
def load_puuids():
    with open("friends_puuids.json", "r") as f:
        return json.load(f)


def save_to_dynamo(match_data):
    """
    Pushes a single match record to DynamoDB.
    Convert the dictionary to a 'Decimal' friendly format for DynamoDB.
    """
    # Convert floats to Decimals (DynamoDB requirement)
    item = json.loads(json.dumps(match_data), parse_float=Decimal)

    try:
        table.put_item(Item=item)
        print(f"Successfully saved Match: {item['matchId']}")
    except Exception as e:
        print(f"Error saving to DynamoDB: {e}")


def get_match_ids(puuid, routing_region, count=5):
    url = f"https://{routing_region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"count": count}
    headers = {"X-Riot-Token": API_KEY}
    response = requests.get(url, headers=headers, params=params)
    return response.json() if response.status_code == 200 else []


def get_match_details(match_id, routing_region, target_puuid):
    url = f"https://{routing_region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": API_KEY}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return None

    data = response.json()
    info = data.get("info", {})
    participants = info.get("participants", [])

    for p in participants:
        if p["puuid"] == target_puuid:
            return {
                "matchId": match_id,  # will be partitionkey
                "puuid": target_puuid,  # will be sort key
                "metadata": {
                    "gameMode": info.get("gameMode"),
                    "timePlayed": p["timePlayed"],  # in seconds
                    "gameEndedInSurrender": p["gameEndedInSurrender"],
                    "teamPosition": p[
                        "teamPosition"
                    ],  # TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY
                },
                "combat": {
                    "kills": p["kills"],
                    "deaths": p["deaths"],
                    "assists": p["assists"],
                    "firstBloodKill": p["firstBloodKill"],
                    # "bountyLevel": p["bountyLevel"], #not working right now
                    "largestCriticalStrike": p["largestCriticalStrike"],
                    "totalDamageTaken": p["totalDamageTaken"],
                    "totalTimeSpentDead": p["totalTimeSpentDead"],
                    "timeCCingOthers": p["timeCCingOthers"],
                    "multikills": {
                        "double": p["doubleKills"],
                        "triple": p["tripleKills"],
                        "quadra": p["quadraKills"],
                        "penta": p["pentaKills"],
                    },
                },
                "objectives": {
                    "damageToTurrets": p["damageDealtToTurrets"],
                    "damageToBuildings": p["damageDealtToBuildings"],
                    "damageToObjectives": p["damageDealtToObjectives"],
                    "baronKills": p["baronKills"],
                    "dragonKills": p["dragonKills"],
                    "objectivesStolen": p["objectivesStolen"],
                    "objectivesStolenAssists": p["objectivesStolenAssists"],
                    "enemyJungleCS": p["totalEnemyJungleMinionsKilled"],
                    "allyJungleCS": p["totalAllyJungleMinionsKilled"],
                },
                "vision_and_social": {
                    "wardsPlaced": p["wardsPlaced"],
                    "wardsKilled": p["wardsKilled"],
                    "sightWardsBought": p["sightWardsBoughtInGame"],
                    "pings": {
                        "assistMe": p["assistMePings"],
                        "command": p["commandPings"],
                        "enemyMissing": p["enemyMissingPings"],
                        "enemyVision": p["enemyVisionPings"],
                        "hold": p["holdPings"],
                        "getBack": p["getBackPings"],
                        "needVision": p["needVisionPings"],
                        "onMyWay": p["onMyWayPings"],
                        "visionCleared": p["visionClearedPings"],
                    },
                },
            }
    return None


def main():
    config = load_config()
    friends_list = load_puuids()
    routing_region = config["settings"]["region"]
    match_limit = config["settings"]["match_count"]

    for name_tag, puuid in friends_list.items():
        print(f"Checking for new matches for {name_tag}...")
        match_ids = get_match_ids(puuid, routing_region, count=match_limit)

        for mid in match_ids:
            # Step 1: Check if match already exists in Dynamo to save API calls
            # (We will add this optimization once the basic version works!)

            # Step 2: Fetch the rich stats we organized
            stats = get_match_details(mid, routing_region, puuid)

            if stats:
                # Step 3: Push to AWS!
                save_to_dynamo(stats)


if __name__ == "__main__":
    main()
