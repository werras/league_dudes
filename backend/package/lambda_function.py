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
    # Get the secret name from the environment variable
    secret_name = os.environ.get("SECRET_NAME")
    region_name = os.environ.get("AWS_REGION", "us-west-1")

    # Create the Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        # Fetch the secret value
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        # Log the error and re-raise it so the Lambda fails visibly
        print(f"Error retrieving secret {secret_name}: {e}")
        raise e

    # Parse the secret string (it comes as a JSON string)
    secret_str = get_secret_value_response["SecretString"]
    secret_dict = json.loads(secret_str)

    #  Return the specific key for Riot
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

    # Run the Shared Logic
    count = league_logic.process_matches(friends, config, riot_api_key, table)

    return {
        "statusCode": 200,
        "body": json.dumps(f"Successfully processed {count} matches"),
    }
