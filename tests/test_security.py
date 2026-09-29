# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import unittest

from alfdockia.community.search.ia.security import SecurityError, require_service_key, resolve_alfresco_authorities, resolve_principal

from .test_utils import settings


class FakeHttp:
    def get(self, url, headers=None, timeout=60):
        if url.endswith("/groups"):
            return {
                "list": {
                    "entries": [
                        {"entry": {"id": "GROUP_EVERYONE"}},
                        {"entry": {"id": "GROUP_site_search-ia"}},
                        {"entry": {"id": "GROUP_site_search-ia_SiteManager"}},
                    ]
                }
            }
        if url.endswith("/sites"):
            return {
                "list": {
                    "entries": [
                        {
                            "entry": {
                                "site": {"id": "search-ia", "role": "SiteManager"},
                                "role": "SiteManager",
                                "id": "search-ia",
                            }
                        }
                    ]
                }
            }
        return {}


class SecurityTest(unittest.TestCase):
    def test_requires_principal_by_default(self) -> None:
        with self.assertRaises(SecurityError):
            resolve_principal({}, {}, settings())

    def test_resolves_user_and_authorities(self) -> None:
        principal = resolve_principal({"user": "maria", "authorities": ["GROUP_FINANCE"]}, {}, settings())

        self.assertFalse(principal.unrestricted)
        self.assertEqual("maria", principal.user)
        self.assertIn("maria", principal.authorities)
        self.assertIn("GROUP_FINANCE", principal.authorities)
        self.assertIn("GROUP_EVERYONE", principal.authorities)

    def test_admin_user_is_unrestricted(self) -> None:
        principal = resolve_principal({"user": "admin"}, {}, settings())

        self.assertTrue(principal.unrestricted)

    def test_resolves_alfresco_authorities_from_repository(self) -> None:
        resolved = resolve_alfresco_authorities(
            "cparedesr",
            settings(
                alfresco_authority_resolution_enabled=True,
                alfresco_username="admin",
                alfresco_password="admin",
            ),
            http=FakeHttp(),
        )

        self.assertIn("GROUP_site_search-ia_SiteManager", resolved)

    def test_service_api_key_is_optional_until_configured(self) -> None:
        require_service_key(settings(), {})

    def test_service_api_key_is_validated_when_configured(self) -> None:
        configured = settings(search_api_key="secret")

        with self.assertRaises(SecurityError):
            require_service_key(configured, {"X-Search-Api-Key": "wrong"})
        require_service_key(configured, {"X-Search-Api-Key": "secret"})


if __name__ == "__main__":
    unittest.main()
