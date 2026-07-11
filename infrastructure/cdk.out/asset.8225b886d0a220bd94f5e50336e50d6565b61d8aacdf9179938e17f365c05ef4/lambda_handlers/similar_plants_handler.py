import json
import os
from typing import Any, Dict
import boto3

from similarity_querying import TrefleClient, get_similar_plants_bundle

_cached_trefle_token = None


def get_trefle_token() -> str:
    """
    Load Trefle token from Secrets Manager in AWS.
    Falls back to TREFLE_TOKEN for local development.
    """
    global _cached_trefle_token

    if _cached_trefle_token:
        return _cached_trefle_token

    local_token = os.getenv("TREFLE_TOKEN")
    if local_token:
        _cached_trefle_token = local_token
        return _cached_trefle_token

    secret_name = os.getenv("TREFLE_SECRET_NAME")
    if not secret_name:
        raise ValueError("Missing TREFLE_SECRET_NAME or TREFLE_TOKEN")

    secrets_client = boto3.client("secretsmanager")
    response = secrets_client.get_secret_value(SecretId=secret_name)

    secret_string = response.get("SecretString")
    if not secret_string:
        raise ValueError("SecretString missing from Secrets Manager response")

    parsed = json.loads(secret_string)

    token = parsed.get("TREFLE_TOKEN")
    if not token:
        raise ValueError("TREFLE_TOKEN missing inside secret JSON")

    _cached_trefle_token = token
    return _cached_trefle_token


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

        client = TrefleClient(token=get_trefle_token())

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