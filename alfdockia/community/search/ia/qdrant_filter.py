# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .filter_contract import encode_qname
from .models import JsonMap, Principal


class QdrantFilterBuilder:
    def build(self, principal: Principal, filters: JsonMap | None = None) -> JsonMap:
        must: list[JsonMap] = [
            match("alive", True),
            match("isFile", True),
        ]
        should: list[JsonMap] = []
        must_not: list[JsonMap] = []

        if not principal.unrestricted:
            if principal.authorities:
                should.append(match_any("readers", principal.authorities))
            else:
                must.append(match("readers", "__no_authority__"))
            must_not.extend(match("denied", authority) for authority in principal.authorities)

        effective_filters = filters or {}
        must.extend(extra_conditions(effective_filters))
        metadata_must, metadata_must_not = metadata_conditions(effective_filters.get("metadata", {}))
        must.extend(metadata_must)
        must_not.extend(metadata_must_not)

        result: JsonMap = {"must": must}
        if should:
            result["should"] = should
        if must_not:
            result["must_not"] = must_not
        return result


def add_full_text_condition(qdrant_filter: JsonMap, query: str) -> JsonMap:
    result = deepcopy(qdrant_filter)
    result.setdefault("must", []).append({"key": "searchText", "match": {"text": query.strip()}})
    return result


def extra_conditions(filters: JsonMap) -> list[JsonMap]:
    conditions: list[JsonMap] = []
    exact_fields = {
        "site": "site",
        "nodeType": "nodeType",
        "type": "type",
        "parentId": "parentId",
        "primaryParent": "primaryParent",
        "ancestorId": "ancestorIds",
        "mimeType": "contentMimeType",
        "contentMimeType": "contentMimeType",
        "aclId": "aclId",
    }
    for source, target in exact_fields.items():
        value = filters.get(source)
        if value is not None and value != "":
            conditions.append(match(target, value))

    add_range(conditions, "createdAt", filters.get("createdFrom"), filters.get("createdTo"))
    add_range(conditions, "modifiedAt", filters.get("modifiedFrom"), filters.get("modifiedTo"))
    return conditions


def metadata_conditions(metadata: JsonMap) -> tuple[list[JsonMap], list[JsonMap]]:
    must: list[JsonMap] = []
    must_not: list[JsonMap] = []
    if not isinstance(metadata, dict):
        return must, must_not
    types = tuple(metadata.get("types", ()))
    aspects = tuple(metadata.get("aspects", ()))
    if types:
        must.append(match_any("nodeType", types))
    if aspects:
        must.append(match_any("aspectNames", aspects))
    for rule in metadata.get("properties", ()):
        compile_property_rule(rule, must, must_not)
    return must, must_not


def compile_property_rule(rule: JsonMap, must: list[JsonMap], must_not: list[JsonMap]) -> None:
    key = encode_qname(rule["name"])
    operator = rule["operator"]
    value = rule.get("value")
    if operator == "eq":
        must.append(match(key, value))
    elif operator == "ne":
        must_not.append(match(key, value))
    elif operator in {"in", "contains_any"}:
        must.append({"key": key, "match": {"any": list(value)}})
    elif operator == "contains_all":
        must.extend(match(key, item) for item in value)
    elif operator == "not_contains":
        must_not.append({"key": key, "match": {"any": list(value)}})
    elif operator == "between":
        must.append({"key": key, "range": {"gte": value[0], "lte": value[1]}})
    elif operator in {"gt", "gte", "lt", "lte"}:
        must.append({"key": key, "range": {operator: value}})
    elif operator == "before":
        must.append({"key": key, "range": {"lt": value}})
    elif operator == "after":
        must.append({"key": key, "range": {"gt": value}})
    elif operator == "exists":
        must_not.append({"is_empty": {"key": key}})
    elif operator == "not_exists":
        must.append({"is_empty": {"key": key}})


def add_range(conditions: list[JsonMap], field: str, gte: Any, lte: Any) -> None:
    range_value: JsonMap = {}
    if gte:
        range_value["gte"] = gte
    if lte:
        range_value["lte"] = lte
    if range_value:
        conditions.append({"key": field, "range": range_value})


def match(key: str, value: Any) -> JsonMap:
    return {"key": key, "match": {"value": value}}


def match_any(key: str, values: tuple[str, ...]) -> JsonMap:
    return {"key": key, "match": {"any": list(values)}}
