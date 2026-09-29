# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.models import QdrantHit
from alfdockia.community.search.ia.relevance import RelevanceDecision, parse_relevance_response, rerank_relevant_hits


class RelevanceTest(unittest.TestCase):
    def test_filters_candidates_that_do_not_satisfy_the_complete_query(self) -> None:
        hits = (
            QdrantHit("temporal", 0.95, {"contentText": "Salario mensual de 1.200 euros."}),
            QdrantHit("indefinido", 0.90, {"contentText": "Salario mensual de 2.400 euros."}),
            QdrantHit("fijo", 0.85, {"contentText": "Salario mensual de 1.400 euros."}),
        )
        decisions = (
            RelevanceDecision("temporal", matches=False, score=0.10),
            RelevanceDecision("indefinido", matches=True, score=0.99),
            RelevanceDecision("fijo", matches=False, score=0.20),
        )

        result = rerank_relevant_hits(hits, decisions, min_score=0.65)

        self.assertEqual(("indefinido",), tuple(hit.point_id for hit in result))

    def test_parses_structured_chat_response(self) -> None:
        decisions = parse_relevance_response(
            {
                "choices": [{"message": {"content": (
                    '{"results":['
                    '{"id":"indefinido","match":true,"score":0.98,"reason":"cumple"},'
                    '{"id":"temporal","match":false,"score":0.05,"reason":"no cumple"}'
                    "]}"
                )}}]
            }
        )

        self.assertEqual(2, len(decisions))
        self.assertTrue(decisions[0].matches)
        self.assertFalse(decisions[1].matches)


if __name__ == "__main__":
    unittest.main()
