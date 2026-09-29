# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.request_parser import parse_search_request

from .test_utils import settings


class RequestParserTest(unittest.TestCase):
    def test_parses_alfresco_search_body(self) -> None:
        request = parse_search_request(
            {
                "query": {"query": "buscame los contratos del 2026", "language": "qdrant-ai"},
                "paging": {"skipCount": 5, "maxItems": 500},
                "include": ["path", "properties"],
                "filters": {"site": "swsdp"},
            },
            {},
            settings(search_max_items_limit=50),
        )

        self.assertEqual("buscame los contratos del 2026", request.query)
        self.assertEqual(5, request.skip_count)
        self.assertEqual(50, request.max_items)
        self.assertEqual(("path", "properties"), request.include)
        self.assertEqual({"site": "swsdp"}, request.filters)

    def test_parses_get_query_params(self) -> None:
        request = parse_search_request({"user": "admin"}, {"q": "contratos", "maxItems": "10"}, settings())

        self.assertEqual("contratos", request.query)
        self.assertEqual(10, request.max_items)

    def test_parses_mode_cursor_and_exact_total_request(self) -> None:
        request = parse_search_request(
            {
                "query": "contratos",
                "mode": "bulk",
                "paging": {"maxItems": 75, "cursor": "opaque", "includeTotal": True},
            },
            {},
            settings(),
        )

        self.assertEqual("bulk", request.mode)
        self.assertEqual("opaque", request.cursor)
        self.assertTrue(request.include_total)
        self.assertEqual(75, request.max_items)

    def test_rejects_unknown_mode_and_deep_offset(self) -> None:
        with self.assertRaises(ValueError):
            parse_search_request({"query": "contratos", "mode": "analytics"}, {}, settings())
        with self.assertRaises(ValueError):
            parse_search_request(
                {"query": "contratos", "paging": {"skipCount": 101}},
                {},
                settings(search_max_items_limit=100),
            )

    def test_ignores_obsolete_generative_performance_overrides(self) -> None:
        request = parse_search_request(
            {
                "query": {"query": "contratos", "language": "alfdokia-ai"},
                "performance": {"rerankCandidates": 30, "candidateTextChars": 1200},
            },
            {},
            settings(),
        )

        self.assertFalse(hasattr(request, "rerank_candidates"))
        self.assertFalse(hasattr(request, "candidate_text_chars"))

    def test_requires_query(self) -> None:
        with self.assertRaises(ValueError):
            parse_search_request({}, {}, settings())

    def test_parses_metadata_contract_from_object_or_json(self) -> None:
        contract = {"version": 1, "types": ["acme:contract"], "aspects": [], "properties": []}
        from_object = parse_search_request(
            {"query": "contratos", "filters": {"metadata": contract}}, {}, settings()
        )
        from_json = parse_search_request(
            {"query": "contratos", "filters": {"metadata": '{"version":1,"types":["acme:contract"]}'}},
            {},
            settings(),
        )

        self.assertEqual(contract, from_object.filters["metadata"])
        self.assertEqual(["acme:contract"], from_json.filters["metadata"]["types"])


if __name__ == "__main__":
    unittest.main()
