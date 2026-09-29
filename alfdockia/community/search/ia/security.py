# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import base64
import logging
from collections.abc import Mapping
from hmac import compare_digest
from typing import Any
from urllib.parse import quote

from .config import Settings
from .http_json import HttpJsonClient, HttpJsonError
from .models import Principal


LOG = logging.getLogger(__name__)


class SecurityError(ValueError):
    pass


def split_authorities(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        separators = [",", ";"]
        values = [value]
        for separator in separators:
            values = [part for item in values for part in item.split(separator)]
        return tuple(item.strip() for item in values if item.strip())
    if isinstance(value, list | tuple | set):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple()


def require_service_key(settings: Settings, headers: Mapping[str, str]) -> None:
    if not settings.search_api_key:
        return
    expected_header = settings.search_api_key_header.lower()
    received = ""
    for key, value in headers.items():
        if key.lower() == expected_header:
            received = value
            break
    if not received or not compare_digest(received, settings.search_api_key):
        raise SecurityError("Invalid search service API key")


def resolve_principal(body: Mapping[str, Any], headers: Mapping[str, str], settings: Settings) -> Principal:
    permissions = body.get("permissions") if isinstance(body.get("permissions"), Mapping) else {}
    explicit_authorities = (
        split_authorities(body.get("authorities"))
        + split_authorities(body.get("authorityIds"))
        + split_authorities(permissions.get("authorities"))
        + split_authorities(permissions.get("authorityIds"))
        + split_authorities(header(headers, "X-Alfresco-Authorities"))
        + split_authorities(header(headers, "X-Authorities"))
    )
    user = first_text(
        body.get("user"),
        body.get("username"),
        permissions.get("user"),
        permissions.get("username"),
        header(headers, "X-Alfresco-User"),
        header(headers, "X-User"),
    )
    resolved_authorities = resolve_alfresco_authorities(user, settings) if user else tuple()
    authorities = unique(
        explicit_authorities
        + resolved_authorities
        + settings.search_default_authorities
        + ((user,) if user else tuple())
    )

    unrestricted = is_unrestricted(user, authorities, body, permissions, settings)
    if settings.search_require_principal and not unrestricted and not user and not explicit_authorities:
        raise SecurityError("Search principal is required to preserve Alfresco permissions")
    if settings.search_require_authorities and not unrestricted and not authorities:
        raise SecurityError("Search authorities are required to preserve Alfresco permissions")
    return Principal(user=user, authorities=authorities, unrestricted=unrestricted)


def resolve_alfresco_authorities(user: str | None, settings: Settings, http: HttpJsonClient | None = None) -> tuple[str, ...]:
    if not user or not settings.alfresco_authority_resolution_enabled:
        return tuple()
    if not settings.alfresco_api_base_url or not settings.alfresco_username or not settings.alfresco_password:
        LOG.warning("Alfresco authority resolution is enabled but ALFRESCO_API_BASE_URL/ALFRESCO_USERNAME/ALFRESCO_PASSWORD are not complete")
        return tuple()

    http = http or HttpJsonClient()
    encoded_user = quote(user, safe="")
    base_url = settings.alfresco_api_base_url.rstrip("/")
    headers = basic_auth_headers(settings.alfresco_username, settings.alfresco_password)
    authorities: list[str] = []

    try:
        groups = http.get(
            base_url + "/-default-/public/alfresco/versions/1/people/" + encoded_user + "/groups",
            headers=headers,
            timeout=settings.alfresco_timeout_seconds,
        )
        authorities.extend(authorities_from_groups_response(groups))
    except HttpJsonError as error:
        LOG.warning("Could not resolve Alfresco groups for user %s: %s", user, error)

    try:
        sites = http.get(
            base_url + "/-default-/public/alfresco/versions/1/people/" + encoded_user + "/sites",
            headers=headers,
            timeout=settings.alfresco_timeout_seconds,
        )
        authorities.extend(authorities_from_sites_response(sites))
    except HttpJsonError as error:
        LOG.warning("Could not resolve Alfresco sites for user %s: %s", user, error)

    resolved = unique(tuple(authorities))
    if resolved:
        LOG.info("Resolved %s Alfresco authorities for user %s", len(resolved), user)
    return resolved


def basic_auth_headers(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode((username + ":" + password).encode("utf-8")).decode("ascii")
    return {"Authorization": "Basic " + token}


def authorities_from_groups_response(response: Mapping[str, Any]) -> list[str]:
    authorities: list[str] = []
    for entry in entries(response):
        authority = text_value(entry.get("id") or entry.get("authorityId") or entry.get("fullName"))
        if authority:
            authorities.append(authority)
    return authorities


def authorities_from_sites_response(response: Mapping[str, Any]) -> list[str]:
    authorities: list[str] = []
    for entry in entries(response):
        site = entry.get("site") if isinstance(entry.get("site"), Mapping) else {}
        site_id = text_value(site.get("id") or entry.get("id") or site.get("shortName") or entry.get("shortName"))
        role = text_value(entry.get("role") or site.get("role") or entry.get("siteRole"))
        if site_id and role:
            authorities.append("GROUP_site_" + site_id + "_" + role)
    return authorities


def entries(response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    list_value = response.get("list") if isinstance(response.get("list"), Mapping) else {}
    raw_entries = list_value.get("entries") if isinstance(list_value, Mapping) else None
    if not isinstance(raw_entries, list):
        raw_entries = response.get("entries")
    if not isinstance(raw_entries, list):
        return []

    result: list[Mapping[str, Any]] = []
    for item in raw_entries:
        if not isinstance(item, Mapping):
            continue
        entry = item.get("entry") if isinstance(item.get("entry"), Mapping) else item
        result.append(entry)
    return result


def text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_unrestricted(
    user: str | None,
    authorities: tuple[str, ...],
    body: Mapping[str, Any],
    permissions: Mapping[str, Any],
    settings: Settings,
) -> bool:
    requested = bool_value(body.get("isAdmin")) or bool_value(body.get("unrestricted")) or bool_value(permissions.get("isAdmin"))
    admin_users = {item.lower() for item in settings.search_admin_users}
    admin_authorities = {item.lower() for item in settings.search_admin_authorities}
    if user and user.lower() in admin_users:
        return True
    if any(authority.lower() in admin_authorities for authority in authorities):
        return True
    return requested and any(authority.lower() in admin_authorities for authority in authorities)


def first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def unique(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)
