import json
import os

import boto3
import league_logic  # Import league logic
from botocore.exceptions import ClientError


def get_secrets():
    """
    Retrieves the Riot API Key from AWS Secrets Manager.
    Assumes the Secret is a JSON object with a key 'RIOT_API_KEY'.
    """
    print("DEBUG: Starting get_secrets()...")

    # 1. Check Environment Variables
    secret_name = os.environ.get("SECRET_NAME")
    region_name = os.environ.get("AWS_REGION", "us-west-1")

    print(
        f"DEBUG: Environment Config - SECRET_NAME: '{secret_name}', REGION: '{region_name}'"
    )

    if not secret_name:
        print("CRITICAL ERROR: SECRET_NAME environment variable is Missing or Empty!")
        # This prevents the specific error you just saw by failing early with a clear message
        raise ValueError("Missing SECRET_NAME environment variable")

    # 2. Create Client
    try:
        session = boto3.session.Session()
        client = session.client(service_name="secretsmanager", region_name=region_name)
        print("DEBUG: Boto3 Secrets Manager client created successfully.")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to create Boto3 client. Details: {e}")
        raise e

    # 3. Fetch Secret
    try:
        print(f"DEBUG: Attempting to fetch secret value for SecretId: {secret_name}")
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        print("DEBUG: Successfully received response from Secrets Manager.")
    except ClientError as e:
        print(
            f"CRITICAL ERROR: AWS ClientError while fetching secret {secret_name}: {e}"
        )
        raise e
    except Exception as e:
        print(f"CRITICAL ERROR: Unexpected error while fetching secret: {e}")
        raise e

    # 4. Parse JSON
    try:
        secret_str = get_secret_value_response["SecretString"]
        # Print length only to verify data existence without leaking secrets
        print(f"DEBUG: SecretString received. Length: {len(secret_str)} characters.")

        secret_dict = json.loads(secret_str)
        print(f"DEBUG: JSON parsing successful. Keys found: {list(secret_dict.keys())}")
    except json.JSONDecodeError as e:
        print(f"CRITICAL ERROR: Secret is not valid JSON. Content: {secret_str}")
        raise e

    # 5. Retrieve Key
    if "RIOT_API_KEY" not in secret_dict:
        print(
            f"CRITICAL ERROR: 'RIOT_API_KEY' not found in secret dictionary. Available keys: {list(secret_dict.keys())}"
        )
        raise KeyError("'RIOT_API_KEY' missing from secret JSON")

    print("DEBUG: RIOT_API_KEY found successfully. Returning value.")
    return secret_dict["RIOT_API_KEY"]


#  Setup AWS Environment
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("TABLE_NAME", "LeagueMatches")
table = dynamodb.Table(TABLE_NAME)


def load_json(filename):
    with open(filename, "r") as f:
        return json.load(f)


def lambda_handler(event, context):
    print("--- STARTING LAMBDA RUN ---")
    riot_api_key = get_secrets()

    # Load Config (Packaged in the zip)
    config = load_json("friends_config.json")
    friends = load_json("friends_puuids.json")
    print(f"DEBUG: Loaded {len(friends)} friends and config settings.")

    # Run the Shared Logic
    count = league_logic.process_matches(friends, config, riot_api_key, table)

    return {
        "statusCode": 200,
        "body": json.dumps(f"Successfully processed {count} matches"),
    }
