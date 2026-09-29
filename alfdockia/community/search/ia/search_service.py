# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import hashlib
import json
import re

from .config import Settings
from .cursor import CursorCodec
from .models import JsonMap, Principal, SearchRequest, SearchResult
from .openai_client import OpenAIEmbeddingClient
from .qdrant_client import QdrantClient
from .qdrant_filter import (
    QdrantFilterBuilder,
    add_full_text_condition,
)
from .relevance import (
    OpenAIRelevanceEvaluator,
    RelevanceError,
    RelevanceEvaluator,
    rerank_relevant_hits,
)


class SemanticSearchService:
    def __init__(
        self,
        settings: Settings,
        embedding_client: OpenAIEmbeddingClient,
        qdrant_client: QdrantClient,
        filter_builder: QdrantFilterBuilder | None = None,
        cursor_codec: CursorCodec | None = None,
        relevance_evaluator: RelevanceEvaluator | None = None,
    ):
        self.settings = settings
        self.embedding_client = embedding_client
        self.qdrant_client = qdrant_client
        self.filter_builder = filter_builder or QdrantFilterBuilder()
        self.cursor_codec = cursor_codec or CursorCodec(
            settings.search_cursor_secret, settings.search_cursor_ttl_seconds
        )
        self.relevance_evaluator = relevance_evaluator or OpenAIRelevanceEvaluator(settings)

    def search(self, request: SearchRequest, principal: Principal) -> SearchResult:
        qdrant_filter = self.filter_builder.build(principal, request.filters)
        bindings = self._bindings(request, principal)
        state = self.cursor_codec.decode(request.cursor, bindings) if request.cursor else {}
        if request.mode == "bulk":
            return self._bulk(request, qdrant_filter, bindings, state)
        if request.skip_count == 0 and is_general_query(request.query):
            general_result = self._general(request, qdrant_filter, bindings, state)
            if general_result is not None:
                return general_result
        return self._interactive(request, principal, qdrant_filter, bindings, state)

    def _general(
        self,
        request: SearchRequest,
        qdrant_filter: JsonMap,
        bindings: dict[str, str],
        state: JsonMap,
    ) -> SearchResult | None:
        effective_filter = add_full_text_condition(
            qdrant_filter, normalize_bulk_query(request.query)
        )
        total = self.qdrant_client.count(effective_filter, exact=True)
        if total == 0:
            return None
        hits, next_offset = self.qdrant_client.scroll(
            effective_filter, request.max_items, state.get("offset")
        )
        cursor = (
            self.cursor_codec.encode(bindings, {"offset": next_offset})
            if next_offset is not None
            else None
        )
        return SearchResult(
            query=request.query,
            skip_count=0,
            max_items=request.max_items,
            total_items=total,
            total_items_exact=True,
            has_more_items=next_offset is not None,
            hits=hits,
            cursor=cursor,
            mode="interactive",
        )

    def _interactive(
        self,
        request: SearchRequest,
        principal: Principal,
        qdrant_filter: JsonMap,
        bindings: dict[str, str],
        state: JsonMap,
    ) -> SearchResult:
        offset = int(state.get("offset", request.skip_count if not request.cursor else 0))
        normalized_query = normalize_bulk_query(request.query)
        vector = self.embedding_client.create_embedding(request.query, user=principal.user)
        requested = offset + max(request.max_items + 1, self.settings.search_rerank_candidates)
        retrieved = self.qdrant_client.hybrid_query(
            vector, normalized_query, qdrant_filter, requested, offset=0
        )
        ordered = self._apply_relevance(request.query, retrieved)
        page_end = offset + request.max_items
        page = ordered[offset:page_end]
        has_more = len(ordered) > page_end
        cursor = self.cursor_codec.encode(
            bindings, {"offset": offset + len(page)}
        ) if has_more else None
        return SearchResult(
            query=request.query,
            skip_count=request.skip_count,
            max_items=request.max_items,
            total_items=None,
            total_items_exact=False,
            has_more_items=has_more,
            hits=page,
            cursor=cursor,
            mode="interactive",
        )

    def _apply_relevance(
        self, query: str, hits: tuple
    ) -> tuple:
        if self.settings.search_relevance_mode in {"", "none", "off", "disabled"}:
            return hits
        if self.settings.search_relevance_mode != "llm":
            raise RelevanceError(
                f"Unsupported SEARCH_RELEVANCE_MODE '{self.settings.search_relevance_mode}'"
            )
        try:
            decisions = self.relevance_evaluator.evaluate(
                query,
                hits,
                candidate_text_chars=self.settings.search_candidate_text_chars,
            )
        except RelevanceError:
            if self.settings.search_relevance_fail_open:
                return hits
            raise
        return rerank_relevant_hits(
            hits, decisions, self.settings.search_relevance_min_score
        )

    def _bulk(
        self,
        request: SearchRequest,
        qdrant_filter: JsonMap,
        bindings: dict[str, str],
        state: JsonMap,
    ) -> SearchResult:
        if request.skip_count:
            raise ValueError("Bulk mode requires cursor pagination; skipCount must be zero")
        effective_filter = add_full_text_condition(qdrant_filter, normalize_bulk_query(request.query))
        total = self.qdrant_client.count(effective_filter, exact=True) if request.include_total else None
        hits, next_offset = self.qdrant_client.scroll(effective_filter, request.max_items, state.get("offset"))
        cursor = self.cursor_codec.encode(bindings, {"offset": next_offset}) if next_offset is not None else None
        return SearchResult(
            query=request.query,
            skip_count=0,
            max_items=request.max_items,
            total_items=total,
            total_items_exact=total is not None,
            has_more_items=next_offset is not None,
            hits=hits,
            cursor=cursor,
            mode="bulk",
        )

    def _bindings(self, request: SearchRequest, principal: Principal) -> dict[str, str]:
        principal_value = {
            "user": principal.user or "",
            "authorities": sorted(principal.authorities),
            "unrestricted": principal.unrestricted,
        }
        return {
            "mode": request.mode,
            "query": _digest(request.query.strip()),
            "filters": _digest(_canonical(request.filters)),
            "principal": _digest(_canonical(principal_value)),
        }


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_BULK_INSTRUCTION_WORDS = frozenset({
    "busca", "buscame", "búscame", "buscar", "encuentra", "encuentrame", "encuéntrame",
    "encuentres", "muestra", "muestrame", "muéstrame", "dame", "quiero", "necesito",
    "todos", "todas", "todo", "toda", "el", "la", "los", "las", "un", "una", "unos",
    "unas", "de", "del", "al", "que", "me", "por", "favor", "sean", "sea",
})

_RESTRICTIVE_QUERY_WORDS = frozenset({
    "antes", "con", "cuya", "cuyas", "cuyo", "cuyos", "después", "despues",
    "desde", "entre", "fecha", "horario", "igual", "importe", "inferior",
    "jornada", "mayor", "menor", "menos", "más", "mas", "mensual", "posterior",
    "remuneración", "remuneracion", "retribución", "retribucion", "salario", "sueldo",
    "superior", "hasta",
})


def normalize_bulk_query(query: str) -> str:
    tokens = re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE)
    meaningful = [token for token in tokens if token not in _BULK_INSTRUCTION_WORDS]
    return " ".join(meaningful) if meaningful else query.strip()


def is_general_query(query: str) -> bool:
    if re.search(r"\d", query):
        return False
    tokens = set(re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE))
    return not tokens.intersection(_RESTRICTIVE_QUERY_WORDS)
