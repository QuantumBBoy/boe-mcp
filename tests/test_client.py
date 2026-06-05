"""Tests for the HTTP client: status mapping, retries, empty results, caching."""

from __future__ import annotations

import httpx
import pytest
import respx

from boe_mcp import client as client_mod
from boe_mcp.client import BASE_URL, BoeNotFoundError, BoeServerError, BoeValidationError


@respx.mock
async def test_get_json_unwraps_data(client):
    respx.get(f"{BASE_URL}/x").mock(
        return_value=httpx.Response(200, json={"status": {"code": "200"}, "data": [{"a": 1}]})
    )
    assert await client.get_json("/x") == [{"a": 1}]
    await client.aclose()


@respx.mock
async def test_empty_data_becomes_empty_list(client):
    respx.get(f"{BASE_URL}/empty").mock(
        return_value=httpx.Response(200, json={"status": {"code": "200"}, "data": ""})
    )
    assert await client.get_json("/empty") == []
    await client.aclose()


@respx.mock
async def test_404_raises_not_found(client):
    respx.get(f"{BASE_URL}/missing").mock(return_value=httpx.Response(404, text="<response/>"))
    with pytest.raises(BoeNotFoundError):
        await client.get_json("/missing")
    await client.aclose()


@respx.mock
async def test_400_raises_validation(client):
    respx.get(f"{BASE_URL}/bad").mock(return_value=httpx.Response(400, text="<response/>"))
    with pytest.raises(BoeValidationError):
        await client.get_json("/bad")
    await client.aclose()


@respx.mock
async def test_5xx_retries_then_succeeds(client, monkeypatch):
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(client_mod.asyncio, "sleep", _no_sleep)
    route = respx.get(f"{BASE_URL}/flaky").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"status": {"code": "200"}, "data": [1]}),
        ]
    )
    assert await client.get_json("/flaky") == [1]
    assert route.call_count == 2
    await client.aclose()


@respx.mock
async def test_5xx_exhausts_retries(client, monkeypatch):
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(client_mod.asyncio, "sleep", _no_sleep)
    respx.get(f"{BASE_URL}/down").mock(return_value=httpx.Response(500))
    with pytest.raises(BoeServerError):
        await client.get_json("/down")
    await client.aclose()


@respx.mock
async def test_cache_avoids_second_request(client):
    route = respx.get(f"{BASE_URL}/ref").mock(
        return_value=httpx.Response(200, json={"status": {"code": "200"}, "data": {"1": "a"}})
    )
    await client.get_json("/ref", cache=True)
    await client.get_json("/ref", cache=True)
    assert route.call_count == 1
    await client.aclose()
