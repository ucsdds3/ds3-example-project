import json
import logging
import os
import time
from typing import Any, Dict
from decimal import Decimal

import boto3
from botocore.config import Config

from similarity_querying import (
    TrefleClient,
    get_similar_plants_bundle,
    get_similar_by_genus,
    get_similar_by_family,
    get_similar_by_distribution,
    get_similar_by_edible_part,
    get_similar_by_growth_habit,
    get_similar_by_growth_form,
    get_similar_by_fruit_color,
)


_cached_trefle_token = None

logger = logging.getLogger("PlantDex")
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def log_step(label: str, start_time: float, **details: Any):
    """Log a timed step with optional context details.

    Args:
        label: Short description of the step being logged.
        start_time: Timestamp captured at the start of the request flow.
        **details: Optional key/value pairs to include in the message.
    """
    elapsed = round(time.time() - start_time, 3)
    message = f"[PlantDex] {label} at {elapsed}s"
    if details:
        detail_text = ", ".join(f"{key}={value}" for key, value in details.items())
        message = f"{message} | {detail_text}"
    logger.info(message)


def summarize_event(event: Any) -> str:
    """Return a compact string preview of an event payload for logging.

    Args:
        event: Lambda event dictionary or payload.

    Returns:
        A short JSON-like preview string suitable for logs.
    """
    if not event:
        return "<empty>"
    try:
        payload = json.dumps(event)
    except Exception:
        return str(event)
    return payload[:1200] if len(payload) > 1200 else payload


def get_trefle_token() -> str:
    """Resolve the Trefle API token from the environment or AWS Secrets Manager.

    Returns:
        A non-empty Trefle token string.

    Raises:
        ValueError: If no token can be resolved from the local environment or secret.
    """
    global _cached_trefle_token

    start = time.time()
    logger.info("[PlantDex] get_trefle_token started")

    if _cached_trefle_token:
        logger.info("[PlantDex] using cached Trefle token")
        return _cached_trefle_token

    local_token = os.getenv("TREFLE_TOKEN")
    if local_token:
        logger.info("[PlantDex] using local env TREFLE_TOKEN")
        _cached_trefle_token = local_token.strip()
        return _cached_trefle_token

    secret_name = os.getenv("TREFLE_SECRET_NAME")
    if not secret_name:
        raise ValueError("Missing TREFLE_SECRET_NAME or TREFLE_TOKEN")

    logger.info("[PlantDex] loading secret: %s", secret_name)

    secrets_client = boto3.client(
        "secretsmanager",
        config=Config(
            connect_timeout=2,
            read_timeout=3,
            retries={"max_attempts": 1},
        ),
    )

    response = secrets_client.get_secret_value(SecretId=secret_name)
    log_step("Secrets Manager returned", start)

    secret_string = response.get("SecretString")
    if not secret_string:
        raise ValueError("SecretString missing from Secrets Manager response")

    parsed = json.loads(secret_string)

    if not isinstance(parsed, dict):
        raise ValueError("SecretString must be JSON object like {'TREFLE_TOKEN':'...'}")

    token = parsed.get("TREFLE_TOKEN")
    if not token:
        raise ValueError("TREFLE_TOKEN missing inside secret JSON")

    _cached_trefle_token = token.strip()
    logger.info("[PlantDex] Trefle token loaded successfully")
    return _cached_trefle_token


_dynamodb_resource = None
_cache_table = None


def get_cache_table():
    """Return the configured DynamoDB cache table, if caching is enabled.

    Returns:
        A DynamoDB table resource or None when cache configuration is missing.
    """
    global _dynamodb_resource
    global _cache_table

    if _cache_table is not None:
        return _cache_table

    table_name = os.getenv("CACHE_TABLE_NAME")
    if not table_name:
        return None

    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb")

    _cache_table = _dynamodb_resource.Table(table_name)
    return _cache_table


def normalize_cache_part(value: Any) -> str:
    """Normalize a cache-key component into a stable, URL-safe string."""
    return str(value).strip().lower().replace(" ", "-")


def build_cache_key(
    query: str,
    basis: str,
    max_results: int,
    image_only: bool,
) -> str:
    """Build a deterministic cache key for a similarity lookup request.

    Args:
        query: Search query string.
        basis: Similarity basis such as genus or family.
        max_results: Maximum number of results requested.
        image_only: Whether image-only filtering was requested.

    Returns:
        A stable cache key string.
    """
    return ":".join(
        [
            "similar",
            normalize_cache_part(query),
            normalize_cache_part(basis),
            str(max_results),
            str(image_only).lower(),
        ]
    )


def get_cached_response(cache_key: str):
    """Read a cached Lambda response from DynamoDB.

    Args:
        cache_key: Cache key associated with the request.

    Returns:
        A parsed cached response body, or None if the item is missing, expired, or unreadable.
    """
    table = get_cache_table()
    if table is None:
        return None

    try:
        item = table.get_item(Key={"cache_key": cache_key}).get("Item")

        if not item:
            return None

        now = int(time.time())
        expires_at = int(item.get("expires_at", 0))

        if expires_at <= now:
            logger.info("[PlantDex] cache expired: %s", cache_key)
            return None

        response_json = item.get("response")
        if not response_json:
            return None

        logger.info("[PlantDex] cache hit: %s", cache_key)
        return json.loads(response_json)

    except Exception as e:
        logger.exception("[PlantDex] cache read error for %s", cache_key)
        return None


def set_cached_response(cache_key: str, response_body: Dict[str, Any]):
    """Store a successful response in DynamoDB cache.

    Args:
        cache_key: Cache key for the response.
        response_body: The response body to serialize and persist.
    """
    table = get_cache_table()
    if table is None:
        return

    try:
        ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
        now = int(time.time())

        table.put_item(
            Item={
                "cache_key": cache_key,
                "response": json.dumps(response_body),
                "created_at": now,
                "expires_at": now + ttl_seconds,
            }
        )

        logger.info("[PlantDex] cache set: %s", cache_key)

    except Exception as e:
        logger.exception("[PlantDex] cache write error for %s", cache_key)


def parse_bool(value: Any, default: bool = False) -> bool:
    """Parse common truthy values from query-string input.

    Args:
        value: The input value to interpret.
        default: Default value returned when the input is None.

    Returns:
        A boolean value for use in request handling.
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """Build a standard API Gateway-compatible Lambda response payload."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    """Handle incoming Lambda events for similar-plant lookups.

    The handler parses query parameters, resolves a Trefle token, performs a similarity
    lookup using the requested basis, and returns a JSON response suitable for API Gateway.

    Args:
        event: Lambda event dictionary containing query-string parameters.
        context: Lambda context object (unused but provided by AWS).

    Returns:
        A dictionary containing statusCode, headers, and a JSON-serialized body.
    """
    start = time.time()
    logger.info("[PlantDex] lambda_handler started")
    logger.info("[PlantDex] event: %s", summarize_event(event))

    try:
        query_params = event.get("queryStringParameters") or {}

        query = query_params.get("query")
        max_results = int(query_params.get("max_results", 10))
        image_only = parse_bool(query_params.get("image_only"), default=False)

        log_step("parsed query params", start, query=query, max_results=max_results, image_only=image_only)

        if not query:
            return response(
                400,
                {
                    "error": "Missing required query parameter: query",
                    "example": "/similar?query=blueberry&basis=genus&max_results=5&image_only=true",
                },
            )

        max_results = max(1, min(max_results, 25))

        token = get_trefle_token()
        log_step("loaded trefle token", start)

        client = TrefleClient(token=token)
        log_step("created TrefleClient", start)

        basis = query_params.get("basis", "genus").strip().lower()
        logger.info("[PlantDex] running similarity lookup | basis=%s query=%s", basis, query)

        cache_key = build_cache_key(
            query=query,
            basis=basis,
            max_results=max_results,
            image_only=image_only,
        )

        cached = get_cached_response(cache_key)
        if cached is not None:
            cached["cache"] = {
                "hit": True,
                "cache_key": cache_key,
            }
            return response(200, cached)

        if basis == "genus":
            result = get_similar_by_genus(
                client=client,
                plant_id_or_query=query,
                max_results=max_results,
                image_only=image_only,
            )

        elif basis == "family":
            result = get_similar_by_family(
                client=client,
                plant_id_or_query=query,
                max_results=max_results,
                image_only=image_only,
                exclude_genus_results=True,
            )

        elif basis == "distribution":
            result = get_similar_by_distribution(
                client=client,
                plant_id_or_query=query,
                max_results=max_results,
                image_only=image_only,
                exclude_genus_and_family_results=True,
                max_zones_to_search=2,
            )

        elif basis == "edible_part":
            result = get_similar_by_edible_part(
                client=client,
                plant_id_or_query=query,
                max_results=max_results,
                image_only=image_only,
            )

        elif basis == "growth_habit":
            result = get_similar_by_growth_habit(
                client=client,
                plant_id_or_query=query,
                max_results=max_results,
                image_only=image_only,
            )

        elif basis == "growth_form":
            result = get_similar_by_growth_form(
                client=client,
                plant_id_or_query=query,
                max_results=max_results,
                image_only=image_only,
            )

        elif basis == "fruit_color":
            result = get_similar_by_fruit_color(
                client=client,
                plant_id_or_query=query,
                max_results=max_results,
                image_only=image_only,
            )

        elif basis == "bundle":
            result = get_similar_plants_bundle(
                client=client,
                plant_id_or_query=query,
                max_results_per_group=max_results,
                image_only=image_only,
            )

        else:
            return response(
                400,
                {
                    "error": f"Unsupported basis: {basis}",
                    "supported_basis": [
                        "genus",
                        "family",
                        "distribution",
                        "edible_part",
                        "growth_habit",
                        "growth_form",
                        "fruit_color",
                        "bundle",
                    ],
                },
            )

        log_step(
            "finished similarity lookup",
            start,
            basis=basis,
            count=result.get("count", 0),
            warnings=result.get("warnings", []),
        )

        result["cache"] = {
            "hit": False,
            "cache_key": cache_key,
        }

        set_cached_response(cache_key, result)

        return response(200, result)

    except Exception as e:
        logger.exception("[PlantDex] handler failed")
        return response(
            500,
            {
                "error": "Internal server error",
                "message": str(e),
            },
        )