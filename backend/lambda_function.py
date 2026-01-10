import json
import os

import boto3
import league_logic  # Import your shared file

# 1. Setup AWS Environment (Injected by Lambda)
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("TABLE_NAME", "LeagueMatches")
table = dynamodb.Table(TABLE_NAME)
API_KEY = os.environ.get("RIOT_API_KEY")


def load_json(filename):
    with open(filename, "r") as f:
        return json.load(f)


def lambda_handler(event, context):
    print("--- STARTING LAMBDA RUN ---")

    # 2. Load Config (Packaged in the zip)
    config = load_json("friends_config.json")
    friends = load_json("friends_puuids.json")

    # 3. Run the Shared Logic
    count = league_logic.process_matches(friends, config, API_KEY, table)

    return {
        "statusCode": 200,
        "body": json.dumps(f"Successfully processed {count} matches"),
    }
