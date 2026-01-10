import json
import os

import boto3
import league_logic  # Imports the file above
from dotenv import load_dotenv

# 1. Load Local Secrets
load_dotenv()
API_KEY = os.getenv("RIOT_API_KEY")

# 2. Connect to AWS (Uses your 'aws configure' profile)
dynamodb = boto3.resource("dynamodb", region_name="us-west-1")
table = dynamodb.Table("LeagueMatches")

# 3. Load Data
# Assumes json files are in the same folder as this script
with open("friends_config.json", "r") as f:
    config = json.load(f)
with open("friends_puuids.json", "r") as f:
    friends = json.load(f)

# 4. Run Logic
print("--- Starting Local Update ---")
league_logic.process_matches(friends, config, API_KEY, table)
print("--- Update Complete ---")
