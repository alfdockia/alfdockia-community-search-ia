# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


JsonMap = dict[str, Any]


@dataclass(frozen=True)
class Principal:
    user: str | None
    authorities: tuple[str, ...]
    unrestricted: bool = False


@dataclass(frozen=True)
class SearchRequest:
    query: str
    skip_count: int
    max_items: int
    include: tuple[str, ...] = tuple()
    fields: tuple[str, ...] = tuple()
    filters: JsonMap = field(default_factory=dict)
    mode: str = "interactive"
    cursor: str | None = None
    include_total: bool = False


@dataclass(frozen=True)
class QdrantHit:
    point_id: str
    score: float
    payload: JsonMap


@dataclass(frozen=True)
class SearchResult:
    query: str
    skip_count: int
    max_items: int
    total_items: int | None
    total_items_exact: bool
    has_more_items: bool
    hits: tuple[QdrantHit, ...]
    cursor: str | None = None
    mode: str = "interactive"
