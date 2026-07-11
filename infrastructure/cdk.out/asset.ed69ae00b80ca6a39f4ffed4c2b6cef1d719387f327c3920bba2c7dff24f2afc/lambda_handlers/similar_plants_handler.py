import json
import os
from typing import Any, Dict

from similarity_querying import TrefleClient, get_similar_plants_bundle


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).lower() in {"true", "1", "yes", "y"}


def response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    """
    Lambda entry point for:

    GET /similar?query=blueberry&max_results=5&image_only=true
    """

    try:
        query_params = event.get("queryStringParameters") or {}

        query = query_params.get("query")
        max_results = int(query_params.get("max_results", 10))
        image_only = parse_bool(query_params.get("image_only"), default=False)

        if not query:
            return response(
                400,
                {
                    "error": "Missing required query parameter: query",
                    "example": "/similar?query=blueberry&max_results=5&image_only=true",
                },
            )

        max_results = max(1, min(max_results, 25))

        client = TrefleClient(token=os.getenv("TREFLE_TOKEN"))

        result = get_similar_plants_bundle(
            client=client,
            plant_id_or_query=query,
            max_results_per_group=max_results,
            image_only=image_only,
        )

        return response(200, result)

    except Exception as e:
        return response(
            500,
            {
                "error": "Internal server error",
                "message": str(e),
            },
        )