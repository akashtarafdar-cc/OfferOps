from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: Any
    headers: dict[str, str]


class HttpError(RuntimeError):
    def __init__(self, message: str, response: HttpResponse | None = None) -> None:
        super().__init__(message)
        self.response = response


class JsonHttpClient:
    def __init__(self, base_url: str = "", headers: dict[str, str] | None = None, timeout: int = 45) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        body = None
        request_headers = {"Accept": "application/json", **self.headers, **(headers or {})}
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return self._parse(response.status, dict(response.headers), response.read())
        except urllib.error.HTTPError as exc:
            parsed = self._parse(exc.code, dict(exc.headers), exc.read())
            raise HttpError(f"{method.upper()} {url} failed with HTTP {exc.code}", parsed) from exc
        except urllib.error.URLError as exc:
            raise HttpError(f"{method.upper()} {url} failed: {exc.reason}") from exc

    def _parse(self, status: int, headers: dict[str, str], raw: bytes) -> HttpResponse:
        if not raw:
            return HttpResponse(status=status, body={}, headers=headers)
        text = raw.decode("utf-8", errors="replace")
        try:
            body: Any = json.loads(text)
        except json.JSONDecodeError:
            body = text
        return HttpResponse(status=status, body=body, headers=headers)

