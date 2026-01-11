import json
import os

import boto3
from boto3.dynamodb.conditions import Attr

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb")
table_name = os.environ["TABLE_NAME"]
table = dynamodb.Table(table_name)


def lambda_handler(event, context):
    try:
        # filter on min date (default to Jan 1, 2026)
        min_date = os.environ.get("MIN_DATE", "2026-01-01")

        # This simple version scans the whole table (ok for small datasets).
        response = table.scan(FilterExpression=Attr("gameDate").gtet(min_date))
        items = response.get("Items", [])

        # Sort items by match creation time if available, or handle in frontend
        items.sort(key=lambda x: x.get("gameEndTimestamp", 0), reverse=True)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                # Enable CORS so your future website can talk to this API
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(items, default=str),  # default=str handles Decimal types
        }

    except Exception as e:
        print(f"Error fetching data: {e}")
        return {"statusCode": 500, "body": json.dumps(f"Error: {str(e)}")}
