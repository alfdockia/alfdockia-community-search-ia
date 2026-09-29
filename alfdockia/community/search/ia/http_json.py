# Copyright (c) 2026 AIgen Technologies S.L
# This file is part of alfdockia-community-search-ia.
# Distributed under the GNU Affero General Public License, version 3.
# See LICENSE and COPYRIGHT for details.

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


JsonMap = dict[str, Any]


class HttpJsonError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class HttpJsonClient:
    def get(self, url: str, headers: JsonMap | None = None, timeout: int = 60) -> JsonMap:
        request = Request(url=url, headers=headers or {}, method="GET")
        return self._send(request, timeout)

    def post(self, url: str, body: JsonMap, headers: JsonMap | None = None, timeout: int = 60) -> JsonMap:
        payload = json.dumps(body).encode("utf-8")
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        request = Request(url=url, data=payload, headers=request_headers, method="POST")
        return self._send(request, timeout)

    def _send(self, request: Request, timeout: int) -> JsonMap:
        try:
            with urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except HTTPError as error:
            response_body = error.read().decode("utf-8", errors="replace")
            raise HttpJsonError(
                f"HTTP {error.code} calling {request.full_url}",
                status_code=error.code,
                response_body=response_body,
            ) from error
        except URLError as error:
            raise HttpJsonError(f"Connection error calling {request.full_url}: {error.reason}") from error
        except json.JSONDecodeError as error:
            raise HttpJsonError(f"Invalid JSON returned by {request.full_url}") from error
