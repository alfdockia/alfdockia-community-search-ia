# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .config import Settings
from .filter_contract import normalize_metadata_filters
from .models import JsonMap, SearchRequest


def parse_search_request(body: JsonMap, params: Mapping[str, Any], settings: Settings) -> SearchRequest:
    query = first_text(
        get_param(params, "q"),
        get_param(params, "query"),
        body.get("q"),
        body.get("text"),
        body.get("userQuery"),
        query_value(body.get("query")),
    )
    if not query:
        raise ValueError("Parameter 'query' or 'q' is required")

    skip_count = int_value(
        get_param(params, "skipCount"),
        body.get("skipCount"),
        nested(body, "paging", "skipCount"),
        default=0,
    )
    max_items = int_value(
        get_param(params, "maxItems"),
        body.get("maxItems"),
        nested(body, "paging", "maxItems"),
        default=settings.search_default_max_items,
    )
    max_items = min(max_items, settings.search_max_items_limit)
    if skip_count > settings.search_legacy_skip_limit:
        raise ValueError("Deep offset pagination is not supported; use paging.cursor")
    mode = first_text(get_param(params, "mode"), body.get("mode")) or "interactive"
    if mode not in {"interactive", "bulk"}:
        raise ValueError("mode must be 'interactive' or 'bulk'")
    cursor = first_text(get_param(params, "cursor"), body.get("cursor"), nested(body, "paging", "cursor"))
    include_total = bool_value(
        get_param(params, "includeTotal"), body.get("includeTotal"), nested(body, "paging", "includeTotal"), default=False
    )

    return SearchRequest(
        query=query,
        skip_count=skip_count,
        max_items=max_items,
        include=string_tuple(body.get("include")),
        fields=string_tuple(body.get("fields")),
        filters=filters_from_body(body),
        mode=mode,
        cursor=cursor,
        include_total=include_total,
    )


def filters_from_body(body: JsonMap) -> JsonMap:
    value = body.get("filters")
    if isinstance(value, dict):
        filters = dict(value)
        if "metadata" in filters:
            filters["metadata"] = normalize_metadata_filters(filters["metadata"])
        return filters
    value = body.get("filter")
    if isinstance(value, dict):
        filters = dict(value)
        if "metadata" in filters:
            filters["metadata"] = normalize_metadata_filters(filters["metadata"])
        return filters
    return {}


def query_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return first_text(value.get("query"), value.get("userQuery"), value.get("text"))
    return None


def nested(body: JsonMap, *keys: str) -> Any:
    current: Any = body
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def get_param(params: Mapping[str, Any], name: str) -> Any:
    value = params.get(name)
    if isinstance(value, list | tuple):
        return value[0] if value else None
    return value


def first_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def int_value(*values: Any, default: int) -> int:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return default
    return default


def optional_int_value(*values: Any, min_value: int = 0, max_value: int | None = None) -> int | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        number = max(min_value, number)
        if max_value is not None:
            number = min(max_value, number)
        return number
    return None


def bool_value(*values: Any, default: bool) -> bool:
    for value in values:
        if isinstance(value, bool):
            return value
        if value is None or value == "":
            continue
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    return default


def string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return tuple()
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())
    if isinstance(value, list | tuple | set):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple()
