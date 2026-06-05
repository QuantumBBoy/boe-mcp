"""Unit tests for the consolidated-legislation query builder."""

from __future__ import annotations

import json

from boe_mcp.query import build_search_query, escape_value


def _q(**kwargs) -> dict:
    return json.loads(build_search_query(**kwargs))


def test_text_searches_title_and_fulltext_and_excludes_repealed():
    inner = _q(text="crisis")["query"]["query_string"]["query"]
    assert "(titulo:crisis or texto:crisis)" in inner
    assert "vigencia_agotada:N" in inner  # repealed excluded by default


def test_include_repealed_drops_vigencia_clause():
    inner = _q(text="crisis", include_repealed=True)["query"]["query_string"]["query"]
    assert "vigencia_agotada" not in inner


def test_code_filters_map_to_fields():
    inner = _q(
        department_code="7723", legal_range_code="1300", matter_code="6658", scope_code="1"
    )["query"]["query_string"]["query"]
    assert "departamento@codigo:7723" in inner
    assert "rango@codigo:1300" in inner
    assert "materia@codigo:6658" in inner
    assert "ambito@codigo:1" in inner


def test_published_range():
    rng = _q(text="x", published_from="2019-01-01", published_to="2019-12-31")["query"]["range"]
    assert rng["fecha_publicacion"] == {"gte": "20190101", "lte": "20191231"}


def test_sort():
    doc = _q(text="x", sort="fecha_publicacion:desc")
    assert doc["sort"] == [{"fecha_publicacion": {"order": "desc"}}]


def test_multiword_text_is_quoted():
    assert escape_value("ley de crisis").startswith('"')
