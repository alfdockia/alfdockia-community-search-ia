# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

from typing import Any

from .models import QdrantHit, SearchResult


JsonMap = dict[str, Any]


class AlfrescoSearchResponseMapper:
    def to_response(self, result: SearchResult) -> JsonMap:
        entries = [{"entry": self._entry(hit)} for hit in result.hits]
        return {
            "list": {
                "pagination": {
                    "count": len(entries),
                    "hasMoreItems": result.has_more_items,
                    "totalItems": result.total_items,
                    "totalItemsExact": result.total_items_exact,
                    "cursor": result.cursor,
                    "skipCount": result.skip_count,
                    "maxItems": result.max_items,
                },
                "context": {
                    "query": {
                        "language": "qdrant-ai",
                        "userQuery": result.query,
                    },
                    "search": {
                        "mode": result.mode,
                    },
                },
                "entries": entries,
            }
        }

    def _entry(self, hit: QdrantHit) -> JsonMap:
        payload = hit.payload
        entry: JsonMap = {
            "id": text(payload, "nodeId", "id", "sys%3Anode%2Duuid") or hit.point_id,
            "name": text(payload, "name", "cm%3Aname") or hit.point_id,
            "nodeType": text(payload, "nodeType", "type", "TYPE") or "cm:content",
            "isFolder": bool(payload.get("isFolder", False)),
            "isFile": bool(payload.get("isFile", True)),
            "search": {
                "score": hit.score,
                "type": "qdrant-ai",
            },
        }
        put(entry, "nodeRef", text(payload, "nodeRef"))
        put(entry, "createdAt", text(payload, "createdAt", "cm%3Acreated"))
        put(entry, "modifiedAt", text(payload, "modifiedAt", "cm%3Amodified"))
        put(entry, "createdByUser", user(payload.get("createdByUser"), text(payload, "cm%3Acreator")))
        put(entry, "modifiedByUser", user(payload.get("modifiedByUser"), text(payload, "cm%3Amodifier")))
        put(entry, "content", content(payload))
        put(entry, "parentId", text(payload, "parentId", "PRIMARYPARENT"))
        put(entry, "path", path(payload))
        put(entry, "aspectNames", list_value(payload.get("aspectNames") or payload.get("ASPECT")))
        put(entry, "properties", properties(payload))
        put(entry, "allowableOperations", ["read"])
        put(entry["search"], "embeddingModel", text(payload, "embeddingModel"))
        put(entry["search"], "embeddingDimension", payload.get("embeddingDimension"))
        return entry


def content(payload: JsonMap) -> JsonMap | None:
    value = payload.get("content")
    result: JsonMap = dict(value) if isinstance(value, dict) else {}
    put(result, "mimeType", payload.get("contentMimeType") or payload.get("cm%3Acontent%2Emimetype"))
    put(result, "mimeTypeName", result.get("mimeTypeName") or result.get("mimeType"))
    put(result, "encoding", payload.get("contentEncoding") or payload.get("cm%3Acontent%2Eencoding"))
    put(result, "sizeInBytes", payload.get("contentSize") or payload.get("cm%3Acontent%2Esize"))
    return result or None


def path(payload: JsonMap) -> JsonMap:
    value = payload.get("path")
    if isinstance(value, dict):
        return value
    name = first_list_item(payload.get("NPATH")) or ""
    return {"name": name, "isComplete": True, "elements": []}


def properties(payload: JsonMap) -> JsonMap:
    value = payload.get("properties")
    if isinstance(value, dict):
        return value
    result: JsonMap = {}
    for key, value in payload.items():
        if "%3A" in key and key not in {
            "sys%3Anode%2Duuid",
            "sys%3Astore%2Dprotocol",
            "sys%3Astore%2Didentifier",
            "cm%3Acontent",
        }:
            result[key] = value
    return result


def user(value: Any, fallback: str | None) -> JsonMap:
    if isinstance(value, dict):
        user_id = value.get("id") or fallback or ""
        display_name = value.get("displayName") or user_id
        return {"id": user_id, "displayName": display_name}
    user_id = fallback or (str(value) if value else "")
    return {"id": user_id, "displayName": user_id}


def text(payload: JsonMap, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            item = first_list_item(value)
            if item:
                return item
        if value is not None and not isinstance(value, dict | list):
            return str(value)
    return None


def list_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def first_list_item(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if item is not None and str(item).strip():
                return str(item)
        return None
    if value is not None and str(value).strip():
        return str(value)
    return None


def put(target: JsonMap, key: str, value: Any) -> None:
    if value is not None:
        target[key] = value
