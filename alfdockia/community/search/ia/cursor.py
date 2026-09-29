# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable, Mapping
from typing import Any


JsonMap = dict[str, Any]


class CursorError(ValueError):
    pass


class CursorCodec:
    def __init__(self, secret: str, ttl_seconds: int, clock: Callable[[], float] | None = None):
        if len(secret.encode("utf-8")) < 16:
            raise ValueError("SEARCH_CURSOR_SECRET must contain at least 16 bytes")
        self._key = secret.encode("utf-8")
        self._ttl_seconds = max(1, ttl_seconds)
        self._clock = clock or time.time

    def encode(self, bindings: Mapping[str, str], state: JsonMap) -> str:
        envelope = {
            "version": 1,
            "expiresAt": int(self._clock()) + self._ttl_seconds,
            "bindings": dict(bindings),
            "state": state,
        }
        payload = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        signature = hmac.new(self._key, payload, hashlib.sha256).digest()
        return _encode(payload) + "." + _encode(signature)

    def decode(self, token: str, bindings: Mapping[str, str]) -> JsonMap:
        try:
            payload_part, signature_part = token.split(".", 1)
            payload = _decode(payload_part)
            signature = _decode(signature_part)
        except (ValueError, TypeError) as error:
            raise CursorError("Cursor no válido") from error
        expected_signature = hmac.new(self._key, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise CursorError("Cursor no válido")
        try:
            envelope = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CursorError("Cursor no válido") from error
        if envelope.get("version") != 1 or int(envelope.get("expiresAt", 0)) <= int(self._clock()):
            raise CursorError("Cursor caducado o incompatible")
        encoded_bindings = json.dumps(envelope.get("bindings", {}), sort_keys=True, separators=(",", ":"))
        expected_bindings = json.dumps(dict(bindings), sort_keys=True, separators=(",", ":"))
        if not hmac.compare_digest(encoded_bindings, expected_bindings):
            raise CursorError("El cursor no pertenece a esta búsqueda")
        state = envelope.get("state")
        if not isinstance(state, dict):
            raise CursorError("Cursor no válido")
        return state


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)
