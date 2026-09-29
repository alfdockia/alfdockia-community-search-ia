# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.main import create_app, search_response_cache_key
from alfdockia.community.search.ia.models import Principal, SearchRequest

from .test_utils import settings


class RouteSurfaceTest(unittest.TestCase):
    def test_exposes_search_but_not_analytics(self) -> None:
        paths = {route.path for route in create_app(settings()).routes}

        self.assertIn("/search", paths)
        self.assertIn("/health", paths)
        self.assertIn("/ready", paths)
        self.assertNotIn("/analytics", paths)

    def test_settings_have_no_analytics_or_admin_event_fields(self) -> None:
        values = vars(settings())

        self.assertFalse(any("analytics" in key for key in values))
        self.assertFalse(any(key.startswith("admin_events_") for key in values))

    def test_cache_separates_modes_cursors_and_total_semantics(self) -> None:
        principal = Principal("maria", ("maria", "GROUP_EVERYONE"))
        interactive = SearchRequest("contratos", 0, 25)
        next_page = SearchRequest("contratos", 0, 25, cursor="signed.page-two")
        bulk = SearchRequest("contratos", 0, 25, mode="bulk", include_total=True)

        keys = {
            search_response_cache_key(interactive, principal),
            search_response_cache_key(next_page, principal),
            search_response_cache_key(bulk, principal),
        }

        self.assertEqual(3, len(keys))


if __name__ == "__main__":
    unittest.main()
