# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import quote

from .config import Settings
from .http_json import HttpJsonClient, HttpJsonError
from .models import QdrantHit
from .qdrant_filter import add_full_text_condition


JsonMap = dict[str, Any]


class QdrantError(RuntimeError):
    pass


class QdrantClient:
    def __init__(self, settings: Settings, http: HttpJsonClient | None = None):
        self.settings = settings
        self.http = http or HttpJsonClient()

    def health(self) -> JsonMap:
        return self.http.get(self._url("/collections/" + self._collection()), self._headers(), self.settings.qdrant_query_timeout_seconds)

    def hybrid_query(
        self,
        vector: list[float],
        text: str,
        qdrant_filter: JsonMap,
        limit: int,
        offset: int = 0,
    ) -> tuple[QdrantHit, ...]:
        effective_filter = deepcopy(qdrant_filter)
        lexical_filter = add_full_text_condition(effective_filter, text)
        prefetch_limit = offset + limit
        body: JsonMap = {
            "prefetch": [
                {
                    "query": vector,
                    "using": self.settings.qdrant_vector_name or "dense",
                    "filter": deepcopy(effective_filter),
                    "limit": prefetch_limit,
                },
                {
                    "query": {
                        "text": text,
                        "model": "qdrant/bm25",
                        "options": {"language": "spanish"},
                    },
                    "using": self.settings.qdrant_sparse_vector_name,
                    "filter": lexical_filter,
                    "limit": prefetch_limit,
                },
            ],
            "query": {"fusion": "rrf"},
            "limit": limit,
            "offset": offset,
            "with_payload": True,
            "with_vector": False,
        }
        if self.settings.qdrant_dense_score_threshold is not None:
            body["prefetch"][0]["score_threshold"] = self.settings.qdrant_dense_score_threshold
        try:
            response = self.http.post(
                self._url("/collections/" + self._collection() + "/points/query"),
                body,
                self._headers(),
                self.settings.qdrant_query_timeout_seconds,
            )
        except HttpJsonError as error:
            raise QdrantError(str(error)) from error
        return parse_query_response(response)

    def count(self, qdrant_filter: JsonMap, exact: bool = True) -> int:
        try:
            response = self.http.post(
                self._url("/collections/" + self._collection() + "/points/count"),
                {"filter": qdrant_filter, "exact": exact},
                self._headers(),
                self.settings.qdrant_query_timeout_seconds,
            )
        except HttpJsonError as error:
            raise QdrantError(str(error)) from error
        result = response.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("count"), int):
            raise QdrantError("Qdrant count response did not contain an integer count")
        return result["count"]

    def scroll(
        self, qdrant_filter: JsonMap, limit: int, offset: str | int | None = None
    ) -> tuple[tuple[QdrantHit, ...], str | int | None]:
        body: JsonMap = {
            "filter": qdrant_filter,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            body["offset"] = offset
        try:
            response = self.http.post(
                self._url("/collections/" + self._collection() + "/points/scroll"),
                body,
                self._headers(),
                self.settings.qdrant_query_timeout_seconds,
            )
        except HttpJsonError as error:
            raise QdrantError(str(error)) from error
        result = response.get("result")
        if not isinstance(result, dict):
            raise QdrantError("Qdrant scroll response did not contain a result object")
        points = result.get("points") if isinstance(result.get("points"), list) else []
        hits = tuple(_point_to_hit(point) for point in points if isinstance(point, dict))
        return hits, result.get("next_page_offset")

    def _headers(self) -> JsonMap:
        headers: JsonMap = {}
        if self.settings.qdrant_api_key:
            headers["api-key"] = self.settings.qdrant_api_key
        return headers

    def _collection(self) -> str:
        return quote(self.settings.qdrant_collection_name, safe="")

    def _url(self, path: str) -> str:
        return self.settings.qdrant_url.rstrip("/") + path


def parse_query_response(response: JsonMap) -> tuple[QdrantHit, ...]:
    result = response.get("result")
    if isinstance(result, dict) and isinstance(result.get("points"), list):
        points = result["points"]
    elif isinstance(result, list):
        points = result
    else:
        points = []

    hits: list[QdrantHit] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        hits.append(_point_to_hit(point))
    return tuple(hits)


def _point_to_hit(point: JsonMap) -> QdrantHit:
    payload = point.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    return QdrantHit(
        point_id=str(point.get("id", "")),
        score=float(point.get("score", 0.0)),
        payload=payload,
    )
