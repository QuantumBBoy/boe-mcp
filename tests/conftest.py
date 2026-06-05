"""Shared test fixtures: recorded BOE response bodies and a client factory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boe_mcp.client import BoeClient

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def load_json(name: str) -> dict:
    return json.loads(load(name))


@pytest.fixture
def client() -> BoeClient:
    # No throttling delay and instant retries keep the offline tests fast.
    return BoeClient(max_retries=2, min_interval=0.0, cache_ttl=60.0)
