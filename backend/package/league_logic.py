import json
from decimal import Decimal

import requests


def get_match_ids(puuid, routing_region, count, api_key):
    """
    Fetches a list of Match IDs for a specific player.
    """
    url = f"https://{routing_region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"count": count}
    headers = {"X-Riot-Token": api_key}
    print(f"DEBUG: Fetching match IDs from {url}")

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            ids = response.json()
            print(f"DEBUG: Found {len(ids)} matches.")
            return ids
        print(
            f"DEBUG: Failed to fetch matches. Status: {response.status_code} Body: {response.text}"
        )
        return []
    except Exception as e:
        print(f"Request failed: {e}")
        return []


def get_match_details(match_id, routing_region, target_puuid, api_key):
    """
    Fetches the deep details of a match and extracts the stats for ONE player.
    """
    url = f"https://{routing_region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": api_key}
    print(f"DEBUG: Fetching details for match {match_id}...")

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to get details for {match_id}: {response.status_code}")
            return None
        data = response.json()
    except Exception as e:
        print(f"Error parsing match {match_id}: {e}")
        return None

    # Safely access the info block
    info = data.get("info", {})
    participants = info.get("participants", [])

    for p in participants:
        if p["puuid"] == target_puuid:

            return {
                # --- DYNAMODB KEYS  ---
                "matchId": match_id,
                "puuid": target_puuid,
                # --- METADATA ---
                "metadata": {
                    "gameMode": info.get("gameMode", "UNKNOWN"),
                    "timePlayed": p.get("timePlayed", 0),
                    "gameEndedInSurrender": p.get("gameEndedInSurrender", False),
                    "teamPosition": p.get("teamPosition", "UNKNOWN"),
                    "championName": p.get("championName", "Unknown"),
                },
                # --- COMBAT STATS ---
                "combat": {
                    "kills": p.get("kills", 0),
                    "deaths": p.get("deaths", 0),
                    "assists": p.get("assists", 0),
                    "kda": round(
                        (p.get("kills", 0) + p.get("assists", 0))
                        / max(1, p.get("deaths", 1)),
                        2,
                    ),
                    "firstBloodKill": p.get("firstBloodKill", False),
                    "largestCriticalStrike": p.get("largestCriticalStrike", 0),
                    "totalDamageDealtToChampions": p.get(
                        "totalDamageDealtToChampions", 0
                    ),
                    "totalDamageTaken": p.get("totalDamageTaken", 0),
                    "totalTimeSpentDead": p.get("totalTimeSpentDead", 0),
                    "timeCCingOthers": p.get("timeCCingOthers", 0),
                    "multikills": {
                        "double": p.get("doubleKills", 0),
                        "triple": p.get("tripleKills", 0),
                        "quadra": p.get("quadraKills", 0),
                        "penta": p.get("pentaKills", 0),
                    },
                },
                # --- OBJECTIVE STATS ---
                "objectives": {
                    "damageToTurrets": p.get("damageDealtToTurrets", 0),
                    "damageToBuildings": p.get("damageDealtToBuildings", 0),
                    "damageToObjectives": p.get("damageDealtToObjectives", 0),
                    "baronKills": p.get("baronKills", 0),
                    "dragonKills": p.get("dragonKills", 0),
                    "objectivesStolen": p.get("objectivesStolen", 0),
                    "objectivesStolenAssists": p.get("objectivesStolenAssists", 0),
                    "enemyJungleCS": p.get("totalEnemyJungleMinionsKilled", 0),
                    "allyJungleCS": p.get("totalAllyJungleMinionsKilled", 0),
                },
                # --- VISION & SOCIAL STATS ---
                "vision_and_social": {
                    "visionScore": p.get("visionScore", 0),
                    "wardsPlaced": p.get("wardsPlaced", 0),
                    "wardsKilled": p.get("wardsKilled", 0),
                    "sightWardsBought": p.get("sightWardsBoughtInGame", 0),
                    "pings": {
                        "assistMe": p.get("assistMePings", 0),
                        "command": p.get("commandPings", 0),
                        "enemyMissing": p.get("enemyMissingPings", 0),
                        "enemyVision": p.get("enemyVisionPings", 0),
                        "hold": p.get("holdPings", 0),
                        "getBack": p.get("getBackPings", 0),
                        "needVision": p.get("needVisionPings", 0),
                        "onMyWay": p.get("onMyWayPings", 0),
                        "visionCleared": p.get("visionClearedPings", 0),
                    },
                },
            }
    print(
        f"DEBUG: Target PUUID {target_puuid} not found in match {match_id} participants."
    )
    return None


def process_matches(friends_list, config, api_key, table_resource):
    """
    Main Logic Controller shared by Local and Lambda.
    """
    routing_region = config["settings"].get("region", "americas")
    match_limit = config["settings"].get("match_count", 5)
    processed = 0

    for name_tag, puuid in friends_list.items():
        print(f"Checking {name_tag}...")
        ids = get_match_ids(puuid, routing_region, match_limit, api_key)
        print(f"DEBUG: Processing {len(ids)} matches for {name_tag}")

        for mid in ids:
            # 1. Fetch the Rich Data
            stats = get_match_details(mid, routing_region, puuid, api_key)

            if stats:
                # 2. Prepare for DynamoDB (Convert Floats to Decimals)
                item = json.loads(json.dumps(stats), parse_float=Decimal)

                try:
                    # 3. Write to Database
                    table_resource.put_item(Item=item)
                    print(f"  > Saved Match {mid} for {name_tag}")
                    processed += 1
                except Exception as e:
                    print(f"  > Error saving {mid}: {e}")

    return processed
