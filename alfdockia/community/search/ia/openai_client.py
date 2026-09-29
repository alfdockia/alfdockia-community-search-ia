# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

from typing import Any

from .config import Settings
from .http_json import HttpJsonClient


class EmbeddingError(RuntimeError):
    pass


class OpenAIEmbeddingClient:
    def __init__(self, settings: Settings, http: HttpJsonClient | None = None):
        self.settings = settings
        self.http = http or HttpJsonClient()

    def create_embedding(self, text: str, user: str | None = None) -> list[float]:
        if not text or not text.strip():
            raise EmbeddingError("Search query cannot be empty")
        if not self.settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY is required")

        body: dict[str, Any] = {
            "model": self.settings.openai_embeddings_model,
            "input": text,
            "encoding_format": self.settings.openai_embeddings_encoding_format,
        }
        if self.settings.openai_embeddings_dimensions is not None:
            body["dimensions"] = self.settings.openai_embeddings_dimensions
        if user:
            body["user"] = user

        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
        if self.settings.openai_api_organization:
            headers["OpenAI-Organization"] = self.settings.openai_api_organization
        if self.settings.openai_api_project:
            headers["OpenAI-Project"] = self.settings.openai_api_project

        response = self.http.post(
            self._url(),
            body,
            headers=headers,
            timeout=self.settings.openai_timeout_seconds,
        )
        return parse_embedding_response(response)

    def _url(self) -> str:
        base = self.settings.openai_api_base_url.rstrip("/")
        path = self.settings.openai_embeddings_path
        if not path.startswith("/"):
            path = "/" + path
        return base + path


def parse_embedding_response(response: dict[str, Any]) -> list[float]:
    data = response.get("data")
    if not isinstance(data, list) or not data:
        raise EmbeddingError("OpenAI embeddings response does not contain data")
    embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
    if not isinstance(embedding, list) or not embedding:
        raise EmbeddingError("OpenAI embeddings response does not contain a vector")

    vector: list[float] = []
    for value in embedding:
        if not isinstance(value, int | float):
            raise EmbeddingError("OpenAI embedding vector contains a non numeric value")
        vector.append(float(value))
    return vector
