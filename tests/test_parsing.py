"""Unit tests for input normalisation and XML parsing."""

from __future__ import annotations

import pytest
from lxml import etree

from boe_mcp.parsing import (
    InvalidInputError,
    aux_table_to_list,
    normalise_date,
    parse_block_xml,
    strip_accents,
    validate_boe_id,
)
from conftest import load


@pytest.mark.parametrize(
    "value,expected",
    [("2023-01-02", "20230102"), ("20230102", "20230102"), ("  2023-01-02 ", "20230102")],
)
def test_normalise_date_ok(value, expected):
    assert normalise_date(value) == expected


@pytest.mark.parametrize("value", ["2023/01/02", "2-1-2023", "abc", "20231301", "20230230"])
def test_normalise_date_rejects(value):
    with pytest.raises(InvalidInputError):
        normalise_date(value)


def test_validate_boe_id_ok():
    assert validate_boe_id("boe-a-2013-5940") == "BOE-A-2013-5940"
    assert validate_boe_id("BOE-S-2015-1") == "BOE-S-2015-1"


@pytest.mark.parametrize("value", ["BOE-XXX", "A-2013-5940", "BOE-A-13-5940", "", "BOE-A-2013-"])
def test_validate_boe_id_rejects(value):
    with pytest.raises(InvalidInputError):
        validate_boe_id(value)


def test_aux_table_dict_to_list_and_filter():
    data = {"5130": "Ministerio de Economía y Hacienda", "7723": "Jefatura del Estado"}
    rows = aux_table_to_list(data, name_filter="hacienda")
    assert rows == [{"codigo": "5130", "texto": "Ministerio de Economía y Hacienda"}]
    assert len(aux_table_to_list(data)) == 2  # no filter → sorted full table


def test_strip_accents():
    assert strip_accents("Protección") == "proteccion"


def test_parse_block_xml():
    tree = etree.fromstring(load("block.xml").encode("utf-8"))
    block = parse_block_xml(tree)
    assert block["id"] == "a1"
    assert block["titulo"] == "Artículo 1"
    assert len(block["versiones"]) == 1
    version = block["versiones"][0]
    assert version["id_norma"] == "BOE-A-2013-5940"
    assert "Esta ley regula la prueba." in version["texto"]
