# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.models import Principal, QdrantHit, SearchRequest
from alfdockia.community.search.ia.relevance import RelevanceDecision
from alfdockia.community.search.ia.search_service import SemanticSearchService, is_general_query

from .test_utils import settings


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def create_embedding(self, query: str, user: str | None = None) -> list[float]:
        self.queries.append(query)
        return [0.1, 0.2, 0.3]


class FakeRelevanceEvaluator:
    def __init__(self, decisions: tuple[RelevanceDecision, ...]) -> None:
        self.decisions = decisions
        self.queries: list[str] = []

    def evaluate(self, query: str, hits: tuple[QdrantHit, ...], candidate_text_chars=None):
        self.queries.append(query)
        return self.decisions


class FakeQdrantClient:
    def __init__(self, hits: tuple[QdrantHit, ...], exact_count: int | None = None):
        self.hits = hits
        self.exact_count = len(hits) if exact_count is None else exact_count
        self.hybrid_filters: list[dict] = []
        self.hybrid_texts: list[str] = []
        self.offsets: list[int] = []
        self.count_filters: list[dict] = []
        self.scroll_filters: list[dict] = []

    def hybrid_query(
        self, vector: list[float], text: str, qdrant_filter: dict, limit: int,
        offset: int = 0,
    ) -> tuple[QdrantHit, ...]:
        self.hybrid_filters.append(qdrant_filter)
        self.hybrid_texts.append(text)
        self.offsets.append(offset)
        return self.hits[offset:offset + limit]

    def count(self, qdrant_filter: dict, exact: bool = True) -> int:
        self.count_filters.append(qdrant_filter)
        return self.exact_count

    def scroll(self, qdrant_filter: dict, limit: int, offset=None):
        self.scroll_filters.append(qdrant_filter)
        start = int(offset or 0)
        page = self.hits[start:start + limit]
        next_offset = start + len(page) if start + len(page) < len(self.hits) else None
        return page, next_offset


class SemanticSearchServiceTest(unittest.TestCase):
    def test_routes_general_examples_away_from_restrictive_queries(self) -> None:
        general = (
            "Búscame los contratos indefinidos",
            "Encuentra contratos temporales por sustitución",
            "Muéstrame contratos fijos discontinuos",
            "Contratos para campañas estacionales",
            "Contratos de duración determinada",
        )
        restrictive = (
            "Contratos indefinidos de jornada completa con salario superior a 1000 euros",
            "Contratos temporales con jornada parcial y horario de mañana",
        )

        self.assertTrue(all(is_general_query(query) for query in general))
        self.assertFalse(any(is_general_query(query) for query in restrictive))

    def test_general_category_search_returns_every_exact_match_without_llm_sampling(self) -> None:
        hits = tuple(
            QdrantHit(str(index), 0.0, {
                "nodeId": str(index),
                "searchText": "Contrato de trabajo indefinido",
            })
            for index in range(30)
        )
        embedding = FakeEmbeddingClient()
        evaluator = FakeRelevanceEvaluator(tuple(
            RelevanceDecision(str(index), index < 14, 0.99 if index < 14 else 0.1)
            for index in range(30)
        ))
        qdrant = FakeQdrantClient(hits)
        service = SemanticSearchService(
            settings(search_relevance_mode="llm"),
            embedding,
            qdrant,
            relevance_evaluator=evaluator,
        )
        principal = Principal("maria", ("maria", "GROUP_EVERYONE"))

        first = service.search(
            SearchRequest("Búscame los contratos indefinidos", 0, 25), principal
        )
        second = service.search(
            SearchRequest("Búscame los contratos indefinidos", 0, 25, cursor=first.cursor),
            principal,
        )

        self.assertEqual(25, len(first.hits))
        self.assertEqual(5, len(second.hits))
        self.assertEqual(30, first.total_items)
        self.assertTrue(first.total_items_exact)
        self.assertEqual([], embedding.queries)
        self.assertEqual([], evaluator.queries)
        self.assertEqual(
            {"key": "searchText", "match": {"text": "contratos indefinidos"}},
            qdrant.scroll_filters[0]["must"][-1],
        )

    def test_interactive_search_filters_arbitrary_natural_language_conditions(self) -> None:
        hits = (
            QdrantHit("temporal", 0.95, {"searchText": "Salario mensual 1.200 euros"}),
            QdrantHit("indefinido", 0.90, {"searchText": "Salario mensual 2.400 euros"}),
            QdrantHit("fijo", 0.85, {"searchText": "Salario mensual 1.400 euros"}),
        )
        evaluator = FakeRelevanceEvaluator((
            RelevanceDecision("temporal", False, 0.05),
            RelevanceDecision("indefinido", True, 0.99),
            RelevanceDecision("fijo", False, 0.10),
        ))
        service = SemanticSearchService(
            settings(search_relevance_mode="llm"),
            FakeEmbeddingClient(),
            FakeQdrantClient(hits),
            relevance_evaluator=evaluator,
        )

        result = service.search(
            SearchRequest("Contratos que cobren más de 1.500 euros al mes", 0, 25),
            Principal("maria", ("maria", "GROUP_EVERYONE")),
        )

        self.assertEqual(("indefinido",), tuple(hit.point_id for hit in result.hits))
        self.assertEqual(["Contratos que cobren más de 1.500 euros al mes"], evaluator.queries)

    def test_interactive_search_combines_embedding_acl_metadata_and_cursor(self) -> None:
        embedding = FakeEmbeddingClient()
        qdrant = FakeQdrantClient(tuple(
            QdrantHit(str(index), 1 - index / 10, {"nodeId": str(index)}) for index in range(4)
        ))
        service = SemanticSearchService(settings(), embedding, qdrant)
        principal = Principal("maria", ("maria", "GROUP_EVERYONE"))
        request = SearchRequest(
            "contratos temporales con jornada parcial", 0, 2,
            filters={"metadata": {"version": 1, "types": ["acme:contract"], "aspects": [], "properties": []}},
        )

        first = service.search(request, principal)
        second = service.search(
            SearchRequest(request.query, 0, 2, filters=request.filters, cursor=first.cursor), principal
        )

        self.assertEqual(
            ["contratos temporales con jornada parcial"] * 2, embedding.queries
        )
        self.assertEqual(
            ["contratos temporales con jornada parcial"] * 2, qdrant.hybrid_texts
        )
        self.assertEqual(["0", "1"], [hit.point_id for hit in first.hits])
        self.assertEqual(["2", "3"], [hit.point_id for hit in second.hits])
        self.assertEqual([0, 0], qdrant.offsets)
        self.assertIsNone(first.total_items)
        self.assertFalse(first.total_items_exact)
        self.assertTrue(first.has_more_items)
        self.assertIn({"key": "nodeType", "match": {"any": ["acme:contract"]}}, qdrant.hybrid_filters[0]["must"])
        self.assertFalse(any(
            condition.get("key") == "searchText"
            for condition in qdrant.hybrid_filters[0]["must"]
        ))
        self.assertEqual("readers", qdrant.hybrid_filters[0]["should"][0]["key"])

    def test_interactive_bm25_ignores_natural_language_instruction_words(self) -> None:
        embedding = FakeEmbeddingClient()
        qdrant = FakeQdrantClient(tuple())
        service = SemanticSearchService(settings(), embedding, qdrant)

        result = service.search(
            SearchRequest("Búscame todos los contratos indefinidos", 0, 25),
            Principal("maria", ("maria", "GROUP_EVERYONE")),
        )

        self.assertEqual(["contratos indefinidos"], qdrant.hybrid_texts)
        self.assertEqual(tuple(), result.hits)
        self.assertFalse(result.has_more_items)

    def test_interactive_nonsense_query_returns_no_repository_documents(self) -> None:
        qdrant = FakeQdrantClient((
            QdrantHit("temporal", 0.20, {"searchText": "Contrato temporal"}),
            QdrantHit("indefinido", 0.18, {"searchText": "Contrato indefinido"}),
        ), exact_count=0)
        evaluator = FakeRelevanceEvaluator((
            RelevanceDecision("temporal", False, 0.0),
            RelevanceDecision("indefinido", False, 0.0),
        ))
        service = SemanticSearchService(
            settings(search_relevance_mode="llm"),
            FakeEmbeddingClient(),
            qdrant,
            relevance_evaluator=evaluator,
        )

        result = service.search(
            SearchRequest("encuentra mecatatuas", 0, 25),
            Principal("maria", ("maria", "GROUP_EVERYONE")),
        )

        self.assertEqual(tuple(), result.hits)
        self.assertFalse(result.has_more_items)
        self.assertEqual(1, len(qdrant.hybrid_filters))

    def test_interactive_search_has_no_global_result_window(self) -> None:
        embedding = FakeEmbeddingClient()
        qdrant = FakeQdrantClient(tuple(
            QdrantHit(str(index), 1.0, {"nodeId": str(index)}) for index in range(1003)
        ))
        service = SemanticSearchService(settings(), embedding, qdrant)
        principal = Principal("maria", ("maria", "GROUP_EVERYONE"))
        cursor = None

        for expected_offset in (0, 250, 500, 750, 1000):
            result = service.search(
                SearchRequest("contratos", 0, 250, cursor=cursor), principal
            )
            cursor = result.cursor

        self.assertEqual(["1000", "1001", "1002"], [hit.point_id for hit in result.hits])
        self.assertEqual(5, len(qdrant.scroll_filters))
        self.assertFalse(result.has_more_items)
        self.assertIsNone(result.cursor)

    def test_bulk_search_uses_full_text_count_and_scroll_without_embedding(self) -> None:
        embedding = FakeEmbeddingClient()
        qdrant = FakeQdrantClient(tuple(
            QdrantHit(str(index), 0.0, {"nodeId": str(index)}) for index in range(5)
        ))
        service = SemanticSearchService(settings(), embedding, qdrant)
        principal = Principal("admin", ("admin",), unrestricted=True)

        result = service.search(
            SearchRequest("Búscame todos los contratos indefinidos", 0, 2, mode="bulk", include_total=True), principal
        )

        self.assertEqual([], embedding.queries)
        self.assertEqual(5, result.total_items)
        self.assertTrue(result.total_items_exact)
        self.assertEqual(["0", "1"], [hit.point_id for hit in result.hits])
        self.assertTrue(result.has_more_items)
        self.assertIsNotNone(result.cursor)
        full_text = {"key": "searchText", "match": {"text": "contratos indefinidos"}}
        self.assertIn(full_text, qdrant.count_filters[0]["must"])
        self.assertEqual(qdrant.count_filters[0], qdrant.scroll_filters[0])


if __name__ == "__main__":
    unittest.main()
