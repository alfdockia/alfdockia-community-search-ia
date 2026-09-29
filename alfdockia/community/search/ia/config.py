# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import os
from dataclasses import dataclass


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return tuple()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(value: str | None, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


@dataclass(frozen=True)
class Settings:
    app_host: str
    app_port: int
    log_level: str

    openai_api_key: str
    openai_api_base_url: str
    openai_api_organization: str
    openai_api_project: str
    openai_embeddings_path: str
    openai_embeddings_model: str
    openai_embeddings_dimensions: int | None
    openai_embeddings_encoding_format: str
    openai_chat_path: str
    openai_chat_model: str
    openai_chat_max_tokens: int
    openai_timeout_seconds: int

    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection_name: str
    qdrant_vector_name: str
    qdrant_sparse_vector_name: str
    qdrant_query_timeout_seconds: int
    qdrant_dense_score_threshold: float | None

    alfresco_api_base_url: str
    alfresco_username: str
    alfresco_password: str
    alfresco_authority_resolution_enabled: bool
    alfresco_timeout_seconds: int

    search_default_max_items: int
    search_max_items_limit: int
    search_default_authorities: tuple[str, ...]
    search_admin_users: tuple[str, ...]
    search_admin_authorities: tuple[str, ...]
    search_require_principal: bool
    search_require_authorities: bool
    search_api_key: str
    search_api_key_header: str
    search_relevance_mode: str
    search_relevance_min_score: float
    search_relevance_fail_open: bool
    search_rerank_candidates: int
    search_candidate_text_chars: int
    search_response_cache_seconds: int
    search_response_cache_size: int
    search_cursor_secret: str
    search_cursor_ttl_seconds: int
    search_legacy_skip_limit: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=_int(os.getenv("APP_PORT"), 8083),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_api_base_url=os.getenv("OPENAI_API_BASE_URL", "https://api.openai.com"),
            openai_api_organization=os.getenv("OPENAI_API_ORGANIZATION", ""),
            openai_api_project=os.getenv("OPENAI_API_PROJECT", ""),
            openai_embeddings_path=os.getenv("OPENAI_EMBEDDINGS_PATH", "/v1/embeddings"),
            openai_embeddings_model=os.getenv("OPENAI_EMBEDDINGS_MODEL", "text-embedding-3-small"),
            openai_embeddings_dimensions=_optional_int(os.getenv("OPENAI_EMBEDDINGS_DIMENSIONS")),
            openai_embeddings_encoding_format=os.getenv("OPENAI_EMBEDDINGS_ENCODING_FORMAT", "float"),
            openai_chat_path=os.getenv("OPENAI_CHAT_PATH", "/v1/chat/completions"),
            openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            openai_chat_max_tokens=_int(os.getenv("OPENAI_CHAT_MAX_TOKENS"), 4000),
            openai_timeout_seconds=_int(os.getenv("OPENAI_TIMEOUT_SECONDS"), 60),
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
            qdrant_collection_name=os.getenv("QDRANT_COLLECTION_NAME", "alfresco-content"),
            qdrant_vector_name=os.getenv("QDRANT_VECTOR_NAME", "dense"),
            qdrant_sparse_vector_name=os.getenv("QDRANT_SPARSE_VECTOR_NAME", "bm25"),
            qdrant_query_timeout_seconds=_int(os.getenv("QDRANT_QUERY_TIMEOUT_SECONDS"), 60),
            qdrant_dense_score_threshold=_float(os.getenv("QDRANT_DENSE_SCORE_THRESHOLD")),
            alfresco_api_base_url=os.getenv("ALFRESCO_API_BASE_URL", "http://host.docker.internal:8080/alfresco/api"),
            alfresco_username=os.getenv("ALFRESCO_USERNAME", ""),
            alfresco_password=os.getenv("ALFRESCO_PASSWORD", ""),
            alfresco_authority_resolution_enabled=_bool(os.getenv("ALFRESCO_AUTHORITY_RESOLUTION_ENABLED"), False),
            alfresco_timeout_seconds=_int(os.getenv("ALFRESCO_TIMEOUT_SECONDS"), 20),
            search_default_max_items=_int(os.getenv("SEARCH_DEFAULT_MAX_ITEMS"), 25),
            search_max_items_limit=_int(os.getenv("SEARCH_MAX_ITEMS_LIMIT"), 100),
            search_default_authorities=_csv(os.getenv("SEARCH_DEFAULT_AUTHORITIES", "GROUP_EVERYONE")),
            search_admin_users=_csv(os.getenv("SEARCH_ADMIN_USERS", "admin,system")),
            search_admin_authorities=_csv(
                os.getenv(
                    "SEARCH_ADMIN_AUTHORITIES",
                    "GROUP_ALFRESCO_ADMINISTRATORS,ALFRESCO_ADMINISTRATORS,ROLE_ADMINISTRATOR",
                )
            ),
            search_require_principal=_bool(os.getenv("SEARCH_REQUIRE_PRINCIPAL"), True),
            search_require_authorities=_bool(os.getenv("SEARCH_REQUIRE_AUTHORITIES"), True),
            search_api_key=os.getenv("SEARCH_API_KEY", ""),
            search_api_key_header=os.getenv("SEARCH_API_KEY_HEADER", "X-Search-Api-Key"),
            search_relevance_mode=os.getenv("SEARCH_RELEVANCE_MODE", "llm").strip().lower(),
            search_relevance_min_score=_float(os.getenv("SEARCH_RELEVANCE_MIN_SCORE")) or 0.65,
            search_relevance_fail_open=_bool(os.getenv("SEARCH_RELEVANCE_FAIL_OPEN"), False),
            search_rerank_candidates=_int(os.getenv("SEARCH_RERANK_CANDIDATES"), 40),
            search_candidate_text_chars=_int(os.getenv("SEARCH_CANDIDATE_TEXT_CHARS"), 2500),
            search_response_cache_seconds=_int(os.getenv("SEARCH_RESPONSE_CACHE_SECONDS"), 0),
            search_response_cache_size=_int(os.getenv("SEARCH_RESPONSE_CACHE_SIZE"), 128),
            search_cursor_secret=os.getenv("SEARCH_CURSOR_SECRET", "change-me-in-production"),
            search_cursor_ttl_seconds=_int(os.getenv("SEARCH_CURSOR_TTL_SECONDS"), 900),
            search_legacy_skip_limit=_int(os.getenv("SEARCH_LEGACY_SKIP_LIMIT"), 100),
        )
