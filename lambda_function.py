import json
import os
from decimal import Decimal

import boto3
import requests

# Initialize DynamoDB outside the handler (Best Practice for connection reuse)
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("TABLE_NAME", "LeagueMatches")
table = dynamodb.Table(TABLE_NAME)

# Riot API Key (Will be set in AWS Console/Terraform)
API_KEY = os.environ.get("RIOT_API_KEY")


def load_config():
    # In Lambda, files in the zip are in the "current directory"
    with open("friends_config.json", "r") as f:
        return json.load(f)


def load_puuids():
    with open("friends_puuids.json", "r") as f:
        return json.load(f)


def save_to_dynamo(match_data):
    # (Same code as before)
    item = json.loads(json.dumps(match_data), parse_float=Decimal)
    try:
        table.put_item(Item=item)
        print(f"Saved: {item['matchId']}")
    except Exception as e:
        print(f"Error saving to DynamoDB: {e}")


def get_match_ids(puuid, routing_region, count):
    # (Same code as before, just remove 'load_dotenv')
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


def lambda_handler(event, context):
    print("Starting League Crawler...")

    config = load_config()
    friends_list = load_puuids()
    routing_region = config["settings"]["region"]
    match_limit = config["settings"]["match_count"]

    matches_processed = 0

    for name_tag, puuid in friends_list.items():
        print(f"Checking {name_tag}...")
        match_ids = get_match_ids(puuid, routing_region, count=match_limit)

        for mid in match_ids:
            # Note: You'll need to copy the full get_match_details logic here
            stats = get_match_details(mid, routing_region, puuid)
            if stats:
                save_to_dynamo(stats)
                matches_processed += 1

    return {
        "statusCode": 200,
        "body": json.dumps(f"Successfully processed {matches_processed} matches"),
    }
