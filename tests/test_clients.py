# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.openai_client import parse_embedding_response
from alfdockia.community.search.ia.qdrant_client import QdrantClient, parse_query_response

from .test_utils import settings


class RecordingHttp:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict, dict, int]] = []

    def post(self, url: str, body: dict, headers: dict, timeout: int) -> dict:
        self.calls.append((url, body, headers, timeout))
        return self.responses.pop(0)

    def get(self, url: str, headers: dict, timeout: int) -> dict:
        return {}


class ClientParsingTest(unittest.TestCase):
    def test_dense_search_is_not_blocked_by_lexical_membership_filter(self) -> None:
        http = RecordingHttp([{"result": {"points": []}}])
        client = QdrantClient(
            settings(qdrant_collection_name="alfresco-content", qdrant_vector_name="dense"), http
        )
        search_filter = {"must": [{"key": "alive", "match": {"value": True}}]}

        client.hybrid_query([0.1, 0.2], "contratos indefinidos", search_filter, 25, offset=50)

        _, body, _, _ = http.calls[0]
        self.assertEqual({"fusion": "rrf"}, body["query"])
        self.assertEqual("dense", body["prefetch"][0]["using"])
        self.assertEqual("bm25", body["prefetch"][1]["using"])
        self.assertEqual([0.1, 0.2], body["prefetch"][0]["query"])
        self.assertEqual("qdrant/bm25", body["prefetch"][1]["query"]["model"])
        self.assertEqual("spanish", body["prefetch"][1]["query"]["options"]["language"])
        self.assertEqual(search_filter, body["prefetch"][0]["filter"])
        self.assertEqual(
            {
                "must": [
                    {"key": "alive", "match": {"value": True}},
                    {"key": "searchText", "match": {"text": "contratos indefinidos"}},
                ]
            },
            body["prefetch"][1]["filter"],
        )
        self.assertEqual(50, body["offset"])
        self.assertEqual(75, body["prefetch"][0]["limit"])
        self.assertEqual(75, body["prefetch"][1]["limit"])
        self.assertNotIn("score_threshold", body["prefetch"][0])
        self.assertNotIn("must_not", body["prefetch"][0]["filter"])
        self.assertFalse(body["with_vector"])

    def test_applies_dense_threshold_only_when_explicitly_configured(self) -> None:
        http = RecordingHttp([{"result": {"points": []}}])
        client = QdrantClient(settings(qdrant_dense_score_threshold=0.72), http)

        client.hybrid_query([0.1, 0.2], "contratos", {"must": []}, 10)

        self.assertEqual(0.72, http.calls[0][1]["prefetch"][0]["score_threshold"])

    def test_counts_and_scrolls_exact_filter_matches(self) -> None:
        http = RecordingHttp([
            {"result": {"count": 501}},
            {"result": {"points": [{"id": "node-1", "payload": {"nodeId": "node-1"}}], "next_page_offset": "node-1"}},
        ])
        client = QdrantClient(settings(qdrant_collection_name="alfresco-content"), http)
        search_filter = {"must": [{"key": "searchText", "match": {"text": "contratos indefinidos"}}]}

        total = client.count(search_filter, exact=True)
        hits, next_offset = client.scroll(search_filter, limit=100, offset=None)

        self.assertEqual(501, total)
        self.assertEqual("node-1", next_offset)
        self.assertEqual("node-1", hits[0].point_id)
        self.assertEqual({"filter": search_filter, "exact": True}, http.calls[0][1])
        self.assertEqual(100, http.calls[1][1]["limit"])
        self.assertFalse(http.calls[1][1]["with_vector"])
        self.assertNotIn("offset", http.calls[1][1])
    def test_parses_openai_embedding_response(self) -> None:
        vector = parse_embedding_response({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

        self.assertEqual([0.1, 0.2, 0.3], vector)

    def test_parses_qdrant_query_response(self) -> None:
        hits = parse_query_response(
            {
                "result": {
                    "points": [
                        {
                            "id": "node-1",
                            "score": 0.97,
                            "payload": {"nodeId": "node-1", "name": "Contrato.pdf"},
                        }
                    ]
                }
            }
        )

        self.assertEqual(1, len(hits))
        self.assertEqual("node-1", hits[0].point_id)
        self.assertEqual(0.97, hits[0].score)
        self.assertEqual("Contrato.pdf", hits[0].payload["name"])

    def test_parses_legacy_qdrant_search_response(self) -> None:
        hits = parse_query_response({"result": [{"id": "node-2", "score": 0.5, "payload": {"nodeId": "node-2"}}]})

        self.assertEqual("node-2", hits[0].point_id)


if __name__ == "__main__":
    unittest.main()
