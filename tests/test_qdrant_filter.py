# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.models import Principal
from alfdockia.community.search.ia.qdrant_filter import QdrantFilterBuilder


class QdrantFilterTest(unittest.TestCase):
    def test_builds_acl_filter_for_regular_user(self) -> None:
        qdrant_filter = QdrantFilterBuilder().build(
            Principal(user="maria", authorities=("maria", "GROUP_EVERYONE", "GROUP_FINANCE")),
            {"site": "swsdp"},
        )

        self.assertIn({"key": "alive", "match": {"value": True}}, qdrant_filter["must"])
        self.assertIn({"key": "isFile", "match": {"value": True}}, qdrant_filter["must"])
        self.assertIn({"key": "site", "match": {"value": "swsdp"}}, qdrant_filter["must"])
        self.assertEqual(
            [{"key": "readers", "match": {"any": ["maria", "GROUP_EVERYONE", "GROUP_FINANCE"]}}],
            qdrant_filter["should"],
        )
        self.assertIn({"key": "denied", "match": {"value": "GROUP_FINANCE"}}, qdrant_filter["must_not"])

    def test_admin_bypasses_acl_filter_but_keeps_content_filters(self) -> None:
        qdrant_filter = QdrantFilterBuilder().build(Principal(user="admin", authorities=("admin",), unrestricted=True))

        self.assertIn({"key": "alive", "match": {"value": True}}, qdrant_filter["must"])
        self.assertIn({"key": "isFile", "match": {"value": True}}, qdrant_filter["must"])
        self.assertNotIn("should", qdrant_filter)
        self.assertNotIn("must_not", qdrant_filter)

    def test_compiles_type_aspect_and_property_intersection(self) -> None:
        qdrant_filter = QdrantFilterBuilder().build(
            Principal(user="maria", authorities=("maria", "GROUP_EVERYONE")),
            {"metadata": {
                "version": 1,
                "types": ["cm:content", "acme:contract"],
                "aspects": ["cm:titled", "acme:legal"],
                "properties": [
                    {"name": "acme:vivienda", "operator": "eq", "value": True, "dataType": "d:boolean"}
                ],
            }},
        )

        self.assertIn(
            {"key": "nodeType", "match": {"any": ["cm:content", "acme:contract"]}},
            qdrant_filter["must"],
        )
        self.assertIn(
            {"key": "aspectNames", "match": {"any": ["cm:titled", "acme:legal"]}},
            qdrant_filter["must"],
        )
        self.assertIn(
            {"key": "q_61636d653a76697669656e6461", "match": {"value": True}},
            qdrant_filter["must"],
        )
        self.assertEqual("readers", qdrant_filter["should"][0]["key"])

    def test_compiles_ranges_existence_and_negation_without_removing_acl(self) -> None:
        qdrant_filter = QdrantFilterBuilder().build(
            Principal(user="maria", authorities=("maria", "GROUP_EVERYONE")),
            {"metadata": {"version": 1, "types": [], "aspects": [], "properties": [
                {"name": "acme:importe", "operator": "between", "value": [1000.0, 5000.0], "dataType": "d:double"},
                {"name": "acme:fecha", "operator": "not_exists", "dataType": "d:date"},
                {"name": "acme:estado", "operator": "ne", "value": "cancelado", "dataType": "d:text"},
            ]}},
        )

        self.assertIn(
            {"key": "q_61636d653a696d706f727465", "range": {"gte": 1000.0, "lte": 5000.0}},
            qdrant_filter["must"],
        )
        self.assertIn({"is_empty": {"key": "q_61636d653a6665636861"}}, qdrant_filter["must"])
        self.assertIn(
            {"key": "q_61636d653a65737461646f", "match": {"value": "cancelado"}},
            qdrant_filter["must_not"],
        )
        self.assertIn(
            {"key": "denied", "match": {"value": "GROUP_EVERYONE"}},
            qdrant_filter["must_not"],
        )


if __name__ == "__main__":
    unittest.main()
