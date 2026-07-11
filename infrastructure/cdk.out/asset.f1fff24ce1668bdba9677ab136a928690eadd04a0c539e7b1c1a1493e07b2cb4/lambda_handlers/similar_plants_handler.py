import json
import os
import time
from typing import Any, Dict

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


def log_step(label: str, start_time: float):
    elapsed = round(time.time() - start_time, 3)
    print(f"[PlantDex] {label} at {elapsed}s")


def get_trefle_token() -> str:
    global _cached_trefle_token

    start = time.time()
    print("[PlantDex] get_trefle_token started")

    if _cached_trefle_token:
        print("[PlantDex] using cached Trefle token")
        return _cached_trefle_token

    local_token = os.getenv("TREFLE_TOKEN")
    if local_token:
        print("[PlantDex] using local env TREFLE_TOKEN")
        _cached_trefle_token = local_token.strip()
        return _cached_trefle_token

    secret_name = os.getenv("TREFLE_SECRET_NAME")
    if not secret_name:
        raise ValueError("Missing TREFLE_SECRET_NAME or TREFLE_TOKEN")

    print(f"[PlantDex] loading secret: {secret_name}")

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
    print("[PlantDex] Trefle token loaded successfully")
    return _cached_trefle_token


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {"true", "1", "yes", "y"}


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
    start = time.time()
    print("[PlantDex] lambda_handler started")
    print("[PlantDex] event:", json.dumps(event)[:1000])

    try:
        query_params = event.get("queryStringParameters") or {}

        query = query_params.get("query")
        max_results = int(query_params.get("max_results", 10))
        image_only = parse_bool(query_params.get("image_only"), default=False)

        log_step("parsed query params", start)

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

        log_step("finished get_similar_plants_bundle", start)

        return response(200, result)

    except Exception as e:
        print("[PlantDex] ERROR:", repr(e))
        return response(
            500,
            {
                "error": "Internal server error",
                "message": str(e),
            },
        )