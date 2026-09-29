# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import json
import logging
import time
from copy import deepcopy
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings
from .models import JsonMap, Principal, SearchRequest
from .openai_client import EmbeddingError, OpenAIEmbeddingClient
from .qdrant_client import QdrantClient, QdrantError
from .request_parser import parse_search_request
from .response_mapper import AlfrescoSearchResponseMapper
from .search_service import SemanticSearchService
from .security import SecurityError, require_service_key, resolve_principal


LOG = logging.getLogger(__name__)
SEARCH_RESPONSE_CACHE: dict[str, tuple[float, JsonMap]] = {}
SEARCH_ALGORITHM_VERSION = 3


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.basicConfig(level=settings.log_level.upper())

    embedding_client = OpenAIEmbeddingClient(settings)
    qdrant_client = QdrantClient(settings)
    search_service = SemanticSearchService(settings, embedding_client, qdrant_client)
    mapper = AlfrescoSearchResponseMapper()
    app = FastAPI(
        title="alfdockia-community-search-ia",
        description="Semantic Alfresco-compatible search backed by OpenAI embeddings and Qdrant.",
        version=__version__,
    )

    @app.get("/health")
    def health() -> JsonMap:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> JsonMap:
        qdrant_client.health()
        return {"status": "ok", "collection": settings.qdrant_collection_name}

    @app.get("/search")
    def search_get(request: Request) -> JSONResponse:
        return execute_search({}, dict(request.query_params), request, settings, search_service, mapper)

    @app.post("/search")
    async def search_post(request: Request) -> JSONResponse:
        body = await json_body(request)
        return execute_search(body, dict(request.query_params), request, settings, search_service, mapper)

    @app.post("/alfresco/api/-default-/public/search/versions/1/search")
    async def alfresco_search_post(request: Request) -> JSONResponse:
        body = await json_body(request)
        return execute_search(body, dict(request.query_params), request, settings, search_service, mapper)

    return app


def execute_search(
    body: JsonMap,
    params: dict[str, Any],
    request: Request,
    settings: Settings,
    search_service: SemanticSearchService,
    mapper: AlfrescoSearchResponseMapper,
) -> JSONResponse:
    start = time.monotonic()
    try:
        headers = dict(request.headers)
        require_service_key(settings, headers)
        search_request = parse_search_request(body, params, settings)
        principal_source = {**params, **body}
        principal = resolve_principal(principal_source, headers, settings)
        log_request_context("search", search_request.query, principal, search_request.filters)
        cache_key = search_response_cache_key(search_request, principal)
        cached_response = get_cached_search_response(cache_key, settings)
        if cached_response is not None:
            LOG.info("AlfDockia search cache hit user=%s query=%s", principal.user, search_request.query)
            return JSONResponse(cached_response)

        result = search_service.search(search_request, principal)
        response_body = mapper.to_response(result)
        cache_search_response(cache_key, response_body, settings)
        LOG.info("AlfDockia search execution millis=%s", int((time.monotonic() - start) * 1000))
        log_result_context("search", result.total_items, result.hits)
        return JSONResponse(response_body)
    except (ValueError, SecurityError) as error:
        return error_response(400, str(error))
    except EmbeddingError as error:
        return error_response(502, str(error))
    except QdrantError as error:
        return error_response(502, str(error))


async def json_body(request: Request) -> JsonMap:
    if not request.headers.get("content-type", "").lower().startswith("application/json"):
        raw = await request.body()
        if not raw:
            return {}
    try:
        value = await request.json()
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "statusCode": status_code,
                "briefSummary": message,
            }
        },
    )


def log_request_context(endpoint: str, query: str, principal, filters: dict[str, Any]) -> None:
    LOG.info(
        "AlfDockia %s request user=%s unrestricted=%s authorities=%s filters=%s query=%s",
        endpoint,
        principal.user,
        principal.unrestricted,
        ",".join(principal.authorities),
        filters,
        query,
    )


def log_result_context(endpoint: str, total_items: int | None, hits: tuple) -> None:
    names = []
    for hit in hits[:10]:
        payload = getattr(hit, "payload", {}) or {}
        names.append(str(payload.get("name") or payload.get("nodeRef") or hit.point_id))
    LOG.info("AlfDockia %s response totalItems=%s hits=%s", endpoint, total_items, ",".join(names))


def search_response_cache_key(search_request: SearchRequest, principal: Principal) -> str:
    return json.dumps(
        {
            "query": search_request.query,
            "skipCount": search_request.skip_count,
            "maxItems": search_request.max_items,
            "filters": search_request.filters,
            "mode": search_request.mode,
            "cursor": search_request.cursor,
            "includeTotal": search_request.include_total,
            "algorithmVersion": SEARCH_ALGORITHM_VERSION,
            "user": principal.user,
            "authorities": sorted(principal.authorities),
            "unrestricted": principal.unrestricted,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def get_cached_search_response(cache_key: str, settings: Settings) -> JsonMap | None:
    if settings.search_response_cache_seconds <= 0 or settings.search_response_cache_size <= 0:
        return None

    cached = SEARCH_RESPONSE_CACHE.get(cache_key)
    if cached is None:
        return None

    created_at, response_body = cached
    if time.monotonic() - created_at > settings.search_response_cache_seconds:
        SEARCH_RESPONSE_CACHE.pop(cache_key, None)
        return None
    return deepcopy(response_body)


def cache_search_response(cache_key: str, response_body: JsonMap, settings: Settings) -> None:
    if settings.search_response_cache_seconds <= 0 or settings.search_response_cache_size <= 0:
        return

    now = time.monotonic()
    for key, (created_at, _) in tuple(SEARCH_RESPONSE_CACHE.items()):
        if now - created_at > settings.search_response_cache_seconds:
            SEARCH_RESPONSE_CACHE.pop(key, None)

    while len(SEARCH_RESPONSE_CACHE) >= settings.search_response_cache_size:
        oldest_key = next(iter(SEARCH_RESPONSE_CACHE), None)
        if oldest_key is None:
            break
        SEARCH_RESPONSE_CACHE.pop(oldest_key, None)

    SEARCH_RESPONSE_CACHE[cache_key] = (now, deepcopy(response_body))


app = create_app()
