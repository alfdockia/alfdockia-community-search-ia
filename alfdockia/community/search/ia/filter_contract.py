# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from .models import JsonMap


MAX_TYPES = 50
MAX_ASPECTS = 50
MAX_PROPERTY_RULES = 20
MAX_VALUE_CHARS = 1024
QNAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*:[A-Za-z_][A-Za-z0-9_.-]*$")
CONTRACT_KEYS = {"version", "types", "aspects", "properties"}
RULE_KEYS = {"name", "operator", "value", "dataType", "multiValued"}
EXISTENCE_OPERATORS = {"exists", "not_exists"}
OPERATORS_BY_KIND = {
    "boolean": {"eq", "ne", *EXISTENCE_OPERATORS},
    "number": {"eq", "ne", "gt", "gte", "lt", "lte", "between", *EXISTENCE_OPERATORS},
    "date": {"eq", "before", "after", "between", *EXISTENCE_OPERATORS},
    "text": {"eq", "ne", "in", "contains_any", "contains_all", "not_contains", *EXISTENCE_OPERATORS},
}
NUMBER_TYPES = {"d:int", "d:long", "d:float", "d:double", "d:decimal"}
DATE_TYPES = {"d:date", "d:datetime"}


class FilterValidationError(ValueError):
    pass


def encode_qname(name: str) -> str:
    return "q_" + name.encode("utf-8").hex()


def normalize_metadata_filters(value: Any) -> JsonMap:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise FilterValidationError("metadata must be valid JSON") from error
    if not isinstance(value, dict):
        raise FilterValidationError("metadata must be an object")
    unknown = set(value) - CONTRACT_KEYS
    if unknown:
        raise FilterValidationError(f"metadata contains unknown fields: {', '.join(sorted(unknown))}")
    if value.get("version", 1) != 1:
        raise FilterValidationError("metadata.version must be 1")

    types = _qname_list(value.get("types", []), "types", MAX_TYPES)
    aspects = _qname_list(value.get("aspects", []), "aspects", MAX_ASPECTS)
    raw_rules = value.get("properties", [])
    if not isinstance(raw_rules, list) or len(raw_rules) > MAX_PROPERTY_RULES:
        raise FilterValidationError(f"metadata.properties must contain at most {MAX_PROPERTY_RULES} rules")
    properties = [_normalize_rule(rule, index) for index, rule in enumerate(raw_rules)]
    return {"version": 1, "types": types, "aspects": aspects, "properties": properties}


def _qname_list(value: Any, field: str, maximum: int) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise FilterValidationError(f"metadata.{field} must be a list with at most {maximum} items")
    result: list[str] = []
    for name in value:
        _require_qname(name, f"metadata.{field}")
        if name not in result:
            result.append(name)
    return result


def _normalize_rule(value: Any, index: int) -> JsonMap:
    label = f"metadata.properties[{index}]"
    if not isinstance(value, dict) or set(value) - RULE_KEYS:
        raise FilterValidationError(f"{label} has an invalid structure")
    name = value.get("name")
    data_type = value.get("dataType", "d:text")
    operator = value.get("operator")
    _require_qname(name, label)
    _require_qname(data_type, label)
    kind = _kind(data_type)
    if operator not in OPERATORS_BY_KIND[kind]:
        raise FilterValidationError(f"{label} uses operator '{operator}' invalid for {data_type}")
    result: JsonMap = {"name": name, "operator": operator, "dataType": data_type}
    if value.get("multiValued"):
        result["multiValued"] = True
    if operator not in EXISTENCE_OPERATORS:
        if "value" not in value:
            raise FilterValidationError(f"{label}.value is required")
        result["value"] = _normalize_value(value["value"], kind, operator, label)
    return result


def _normalize_value(value: Any, kind: str, operator: str, label: str) -> Any:
    list_operator = operator in {"between", "in", "contains_any", "contains_all", "not_contains"}
    if list_operator:
        if not isinstance(value, list) or not value or (operator == "between" and len(value) != 2):
            raise FilterValidationError(f"{label}.value must be a non-empty list")
        return [_scalar(item, kind, label) for item in value]
    return _scalar(value, kind, label)


def _scalar(value: Any, kind: str, label: str) -> Any:
    if kind == "boolean":
        if not isinstance(value, bool):
            raise FilterValidationError(f"{label}.value must be boolean")
        return value
    if kind == "number":
        if isinstance(value, bool):
            raise FilterValidationError(f"{label}.value must be numeric")
        try:
            return float(value)
        except (TypeError, ValueError) as error:
            raise FilterValidationError(f"{label}.value must be numeric") from error
    text = str(value).strip() if value is not None else ""
    if not text or len(text) > MAX_VALUE_CHARS:
        raise FilterValidationError(f"{label}.value must contain 1-{MAX_VALUE_CHARS} characters")
    if kind == "date":
        try:
            datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as error:
            raise FilterValidationError(f"{label}.value must be ISO-8601") from error
    return text


def _kind(data_type: str) -> str:
    if data_type == "d:boolean":
        return "boolean"
    if data_type in NUMBER_TYPES:
        return "number"
    if data_type in DATE_TYPES:
        return "date"
    return "text"


def _require_qname(value: Any, label: str) -> None:
    if not isinstance(value, str) or not QNAME.fullmatch(value):
        raise FilterValidationError(f"{label} contains an invalid QName")
