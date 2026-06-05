"""Tests for tool behaviour: summary flattening, search and lookups via mocked HTTP."""

from __future__ import annotations

import httpx
import respx

from boe_mcp.client import BASE_URL
from boe_mcp.parsing import aux_table_to_list
from boe_mcp.tools.summaries import flatten_summary
from conftest import load_json


def test_flatten_summary_handles_epigrafe_and_direct_items():
    result = flatten_summary(load_json("summary.json")["data"], "20230102", None, None)
    assert result.total_items == 2
    ids = {i.identificador for i in result.items}
    assert ids == {"BOE-A-2023-1", "BOE-A-2023-2"}
    first = next(i for i in result.items if i.identificador == "BOE-A-2023-1")
    assert first.url_pdf == "https://www.boe.es/x/BOE-A-2023-1.pdf"  # extracted from dict
    assert first.epigrafe == "Medidas"
    assert result.publicacion == "BOE"


def test_flatten_summary_section_filter_and_max_items():
    data = load_json("summary.json")["data"]
    filtered = flatten_summary(data, "20230102", "Disposiciones generales", None)
    assert filtered.total_items == 2
    capped = flatten_summary(data, "20230102", None, 1)
    assert capped.total_items == 2 and len(capped.items) == 1


def test_aux_table_to_list_from_fixture():
    rows = aux_table_to_list(load_json("departamentos.json")["data"], "datos")
    assert rows == [{"codigo": "1011", "texto": "Agencia Española de Protección de Datos"}]


@respx.mock
async def test_search_legislation_builds_request_and_parses(client):
    route = respx.get(f"{BASE_URL}/legislacion-consolidada").mock(
        return_value=httpx.Response(200, json=load_json("search.json"))
    )
    data = await client.get_json(
        "/legislacion-consolidada", params={"query": "{}", "offset": 0, "limit": 25}
    )
    assert route.called
    assert data[0]["identificador"] == "BOE-A-2013-5940"
    await client.aclose()
