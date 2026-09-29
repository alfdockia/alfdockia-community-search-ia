# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .config import Settings
from .http_json import HttpJsonClient, HttpJsonError
from .models import JsonMap, QdrantHit


class RelevanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class RelevanceDecision:
    point_id: str
    matches: bool
    score: float
    reason: str = ""


class RelevanceEvaluator(Protocol):
    def evaluate(
        self,
        query: str,
        hits: tuple[QdrantHit, ...],
        candidate_text_chars: int | None = None,
    ) -> tuple[RelevanceDecision, ...]:
        pass


class OpenAIRelevanceEvaluator:
    """Filters Qdrant candidates against the complete natural-language predicate."""

    def __init__(self, settings: Settings, http: HttpJsonClient | None = None):
        self.settings = settings
        self.http = http or HttpJsonClient()

    def evaluate(
        self,
        query: str,
        hits: tuple[QdrantHit, ...],
        candidate_text_chars: int | None = None,
    ) -> tuple[RelevanceDecision, ...]:
        if not hits:
            return tuple()
        if not self.settings.openai_api_key:
            raise RelevanceError("OPENAI_API_KEY is required for relevance evaluation")

        text_chars = candidate_text_chars or self.settings.search_candidate_text_chars
        body: JsonMap = {
            "model": self.settings.openai_chat_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Eres un filtro estricto de búsqueda documental. Evalúa de forma independiente "
                        "si cada documento satisface la consulta completa. Comprueba tipo documental, "
                        "significado, importes, comparaciones, fechas, jornadas y cualquier otra condición "
                        "solicitada usando exclusivamente el texto y los metadatos suministrados. "
                        "Acepta sinónimos y expresiones equivalentes, pero no inventes datos. "
                        "Devuelve solo JSON válido con esta forma: "
                        '{"results":[{"id":"...","match":true,"score":0.0,"reason":"..."}]}'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "query": query,
                            "candidates": [candidate_summary(hit, text_chars) for hit in hits],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        if self.settings.openai_chat_max_tokens > 0:
            body["max_tokens"] = self.settings.openai_chat_max_tokens

        try:
            response = self.http.post(
                self._url(),
                body,
                self._headers(),
                self.settings.openai_timeout_seconds,
            )
        except HttpJsonError as error:
            detail = f": {error.response_body}" if error.response_body else ""
            raise RelevanceError(f"OpenAI relevance evaluation failed{detail}") from error
        return parse_relevance_response(response)

    def _headers(self) -> JsonMap:
        headers: JsonMap = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
        if self.settings.openai_api_organization:
            headers["OpenAI-Organization"] = self.settings.openai_api_organization
        if self.settings.openai_api_project:
            headers["OpenAI-Project"] = self.settings.openai_api_project
        return headers

    def _url(self) -> str:
        path = self.settings.openai_chat_path
        return self.settings.openai_api_base_url.rstrip("/") + (path if path.startswith("/") else "/" + path)


def rerank_relevant_hits(
    hits: tuple[QdrantHit, ...],
    decisions: tuple[RelevanceDecision, ...],
    min_score: float,
) -> tuple[QdrantHit, ...]:
    by_id = {decision.point_id: decision for decision in decisions}
    relevant: list[tuple[float, float, int, QdrantHit]] = []
    for index, hit in enumerate(hits):
        decision = by_id.get(hit.point_id)
        if decision is None or not decision.matches or decision.score < min_score:
            continue
        relevant.append((decision.score, hit.score, index, hit))
    relevant.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return tuple(item[3] for item in relevant)


def candidate_summary(hit: QdrantHit, max_chars: int) -> JsonMap:
    payload = hit.payload
    text = _collapse_whitespace(" ".join(_text_values([
        payload.get(key) for key in (
            "name", "title", "description", "searchText", "contentText", "properties", "eventProperties"
        )
    ])))
    if max_chars > 0:
        text = text[:max_chars]
    return {
        "id": hit.point_id,
        "vectorScore": hit.score,
        "name": str(payload.get("name") or hit.point_id),
        "nodeType": str(payload.get("nodeType") or payload.get("type") or ""),
        "text": text,
    }


def parse_relevance_response(response: JsonMap) -> tuple[RelevanceDecision, ...]:
    choices = response.get("choices")
    message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise RelevanceError("OpenAI relevance response does not contain message content")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise RelevanceError("OpenAI relevance response is not valid JSON")
        parsed = json.loads(content[start:end + 1])
    items = parsed.get("results") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        raise RelevanceError("OpenAI relevance response does not contain a results list")

    decisions: list[RelevanceDecision] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        point_id = str(item.get("id") or "").strip()
        if not point_id:
            continue
        matches = item.get("match") is True or str(item.get("match", "")).casefold() in {"true", "1", "yes", "si", "sí"}
        try:
            score = float(item.get("score", 1.0 if matches else 0.0))
        except (TypeError, ValueError):
            score = 1.0 if matches else 0.0
        decisions.append(RelevanceDecision(point_id, matches, max(0.0, min(1.0, score)), str(item.get("reason") or "")))
    return tuple(decisions)


def _text_values(values: Any) -> list[str]:
    result: list[str] = []

    def collect(value: Any) -> None:
        if value is None or isinstance(value, bool):
            return
        if isinstance(value, (str, int, float)):
            result.append(str(value))
        elif isinstance(value, dict):
            for key, item in value.items():
                result.append(str(key))
                collect(item)
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                collect(item)

    collect(values)
    return result


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
