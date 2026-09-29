# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.models import QdrantHit, SearchResult
from alfdockia.community.search.ia.response_mapper import AlfrescoSearchResponseMapper


class ResponseMapperTest(unittest.TestCase):
    def test_maps_qdrant_payload_to_alfresco_search_response(self) -> None:
        result = SearchResult(
            query="contratos 2026",
            skip_count=0,
            max_items=25,
            total_items=1,
            total_items_exact=True,
            has_more_items=False,
            cursor=None,
            hits=(
                QdrantHit(
                    point_id="4aba",
                    score=0.91,
                    payload={
                        "nodeId": "4aba",
                        "nodeRef": "workspace://SpacesStore/4aba",
                        "name": "01_contrato_trabajo_indefinido.pdf",
                        "nodeType": "cm:content",
                        "isFile": True,
                        "isFolder": False,
                        "createdAt": "2026-08-28T18:31:01.155+0000",
                        "modifiedAt": "2026-08-28T18:31:01.155+0000",
                        "createdByUser": {"id": "admin", "displayName": "Administrator"},
                        "modifiedByUser": {"id": "admin", "displayName": "Administrator"},
                        "parentId": "parent-1",
                        "path": {"name": "/Company Home/Shared", "isComplete": True, "elements": []},
                        "aspectNames": ["cm:auditable"],
                        "properties": {"cm:versionLabel": "1.0"},
                        "content": {
                            "mimeType": "application/pdf",
                            "mimeTypeName": "Adobe PDF Document",
                            "sizeInBytes": 1928719,
                            "encoding": "UTF-8",
                        },
                        "embeddingModel": "text-embedding-3-small",
                        "embeddingDimension": 1536,
                    },
                ),
            ),
        )

        response = AlfrescoSearchResponseMapper().to_response(result)

        self.assertEqual(1, response["list"]["pagination"]["count"])
        entry = response["list"]["entries"][0]["entry"]
        self.assertEqual("4aba", entry["id"])
        self.assertEqual("01_contrato_trabajo_indefinido.pdf", entry["name"])
        self.assertEqual("cm:content", entry["nodeType"])
        self.assertEqual("application/pdf", entry["content"]["mimeType"])
        self.assertEqual(0.91, entry["search"]["score"])
        self.assertTrue(response["list"]["pagination"]["totalItemsExact"])
        self.assertIsNone(response["list"]["pagination"]["cursor"])


if __name__ == "__main__":
    unittest.main()
