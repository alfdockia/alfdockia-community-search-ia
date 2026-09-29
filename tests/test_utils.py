# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

from dataclasses import replace

from alfdockia.community.search.ia.config import Settings


def settings(**overrides) -> Settings:
    base = Settings(
        app_host="0.0.0.0",
        app_port=8083,
        log_level="INFO",
        openai_api_key="test-openai-key",
        openai_api_base_url="https://api.openai.test",
        openai_api_organization="",
        openai_api_project="",
        openai_embeddings_path="/v1/embeddings",
        openai_embeddings_model="text-embedding-3-small",
        openai_embeddings_dimensions=None,
        openai_embeddings_encoding_format="float",
        openai_chat_path="/v1/chat/completions",
        openai_chat_model="gpt-4o-mini",
        openai_chat_max_tokens=4000,
        openai_timeout_seconds=60,
        qdrant_url="http://qdrant.test:6333",
        qdrant_api_key="",
        qdrant_collection_name="alfresco-content",
        qdrant_vector_name="",
        qdrant_sparse_vector_name="bm25",
        qdrant_query_timeout_seconds=60,
        qdrant_dense_score_threshold=None,
        alfresco_api_base_url="http://alfresco.test/alfresco/api",
        alfresco_username="",
        alfresco_password="",
        alfresco_authority_resolution_enabled=False,
        alfresco_timeout_seconds=20,
        search_default_max_items=25,
        search_max_items_limit=100,
        search_default_authorities=("GROUP_EVERYONE",),
        search_admin_users=("admin", "system"),
        search_admin_authorities=("GROUP_ALFRESCO_ADMINISTRATORS", "ALFRESCO_ADMINISTRATORS", "ROLE_ADMINISTRATOR"),
        search_require_principal=True,
        search_require_authorities=True,
        search_api_key="",
        search_api_key_header="X-Search-Api-Key",
        search_relevance_mode="off",
        search_relevance_min_score=0.65,
        search_relevance_fail_open=False,
        search_rerank_candidates=40,
        search_candidate_text_chars=2500,
        search_response_cache_seconds=15,
        search_response_cache_size=128,
        search_cursor_secret="a-test-secret-with-enough-entropy",
        search_cursor_ttl_seconds=900,
        search_legacy_skip_limit=100,
    )
    return replace(base, **overrides)
