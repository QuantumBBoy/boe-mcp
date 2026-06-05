"""Async HTTP client for the BOE open-data API.

Responsibilities:
- Negotiate JSON vs XML via the ``Accept`` header (some endpoints are XML-only).
- Map HTTP status codes to typed errors with actionable messages.
- Retry transient 5xx/timeout failures with exponential back-off.
- Self-throttle (the BOE may suspend abusive clients) and cache slow-changing resources.

Be a good API citizen: a descriptive, contactable User-Agent and modest concurrency.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from lxml import etree

from . import __version__

BASE_URL = "https://www.boe.es/datosabiertos/api"
USER_AGENT = f"boe-mcp/{__version__} (+https://github.com/estoreasoporte/BoeMCP)"


class BoeError(Exception):
    """Base class for BOE API errors."""


class BoeNotFoundError(BoeError):
    """HTTP 404 — no norm/summary exists for the requested id or date."""


class BoeValidationError(BoeError):
    """HTTP 400 — the BOE rejected the request parameters."""


class BoeServerError(BoeError):
    """HTTP 5xx — the BOE service failed after retries."""


class _TTLCache:
    """Tiny in-process TTL cache keyed by request path+params."""

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        hit = self._store.get(key)
        if hit is None:
            return None
        expires_at, value = hit
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)


class BoeClient:
    """Async wrapper around the BOE open-data REST API."""

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
        max_concurrency: int = 4,
        min_interval: float = 0.1,
        cache_ttl: float = 3600.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._min_interval = min_interval
        self._last_request = 0.0
        self._cache = _TTLCache(cache_ttl)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "BoeClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()

    @staticmethod
    def _raise_for_status(response: httpx.Response, path: str) -> None:
        code = response.status_code
        if code < 400:
            return
        if code == 404:
            raise BoeNotFoundError(f"Nothing found for {path!r}.")
        if code == 400:
            raise BoeValidationError(f"The BOE rejected the request for {path!r} (bad parameters).")
        if code == 403:
            # Only GET is allowed by the API; a 403 means an internal misuse.
            raise BoeError(f"Forbidden request to {path!r} (only GET is supported).")
        if code >= 500:
            raise BoeServerError(f"BOE service error {code} for {path!r}.")
        raise BoeError(f"Unexpected HTTP {code} for {path!r}.")

    async def _request(self, path: str, *, accept: str, params: dict[str, Any] | None) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            async with self._semaphore:
                await self._throttle()
                try:
                    response = await self._client.get(
                        path, params=params, headers={"Accept": accept}
                    )
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_exc = exc
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    raise BoeServerError(f"Network error contacting BOE for {path!r}: {exc}") from exc

            if response.status_code >= 500 and attempt < self._max_retries - 1:
                await asyncio.sleep(2**attempt)
                continue
            self._raise_for_status(response, path)
            return response

        # Exhausted retries on 5xx.
        if last_exc:
            raise BoeServerError(f"BOE unreachable for {path!r}.") from last_exc
        raise BoeServerError(f"BOE service repeatedly failed for {path!r}.")

    async def get_json(
        self, path: str, *, params: dict[str, Any] | None = None, cache: bool = False
    ) -> Any:
        """GET ``path`` requesting JSON; return the unwrapped ``data`` payload.

        Returns ``[]`` when the BOE answers 200 with an empty ``data`` (its "no results" shape).
        """
        cache_key = f"json:{path}:{params}" if cache else None
        if cache_key:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        response = await self._request(path, accept="application/json", params=params)
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else payload
        if data == "" or data is None:
            data = []
        if cache_key:
            self._cache.set(cache_key, data)
        return data

    async def get_xml(
        self, path: str, *, params: dict[str, Any] | None = None, cache: bool = False
    ) -> etree._Element:
        """GET ``path`` requesting XML; return the parsed root element."""
        cache_key = f"xml:{path}:{params}" if cache else None
        if cache_key:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        response = await self._request(path, accept="application/xml", params=params)
        root = etree.fromstring(response.content)
        if cache_key:
            self._cache.set(cache_key, root)
        return root
