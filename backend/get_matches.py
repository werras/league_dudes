import json
import os

import boto3
from boto3.dynamodb.conditions import Attr

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")
table_name = os.environ["TABLE_NAME"]
table = dynamodb.Table(table_name)


def lambda_handler(event, context):
    print("DEBUG: Starting get_matches lambda_handler")
    try:
        # filter on min date (default to Jan 1, 2026)
        min_date = os.environ.get("MIN_GAME_DATE", "2026-01-01")
        print(f"DEBUG: Using MIN_GAME_DATE: {min_date}")

        # This simple version scans the whole table (ok for small datasets).
        print(f"DEBUG: Scanning table: {table_name}")
        response = table.scan(FilterExpression=Attr("gameDate").gte(min_date))
        items = response.get("Items", [])
        print(f"DEBUG: Scan complete. Found {len(items)} items.")

        # Sort items by match end time if available, or handle in frontend
        items.sort(key=lambda x: x.get("gameEndTimestamp", 0), reverse=True)

        return {
            "statusCode": 200,
            "body": json.dumps(items, default=str),  # default=str handles Decimal types
        }

    except Exception as e:
        print(f"Error fetching data: {e}")
        return {"statusCode": 500, "body": json.dumps(f"Error: {str(e)}")}
