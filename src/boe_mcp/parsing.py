"""Input normalisation and XML→dict helpers for the BOE API.

The BOE API mixes JSON and XML: list/metadata/analysis/index endpoints speak JSON, but the
consolidated *text* endpoints (`/texto`, `/texto/bloque/{id}`) are XML-only. These helpers
normalise user input (dates, identifiers) before any HTTP call and turn the XML-only payloads
into plain dicts the model can consume.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

from lxml import etree

# BOE-A-2015-10566 (disposition) / BOE-S-2015-1 (summary) — letter section, year, sequence.
_BOE_ID_RE = re.compile(r"^BOE-[A-Z]-\d{4}-\d+$")
_DATE_COMPACT_RE = re.compile(r"^\d{8}$")
_DATE_ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class InvalidInputError(ValueError):
    """Raised when a user-supplied date or identifier is malformed (before any HTTP call)."""


def normalise_date(value: str) -> str:
    """Normalise ``YYYY-MM-DD`` or ``YYYYMMDD`` to the BOE ``AAAAMMDD`` form.

    Raises :class:`InvalidInputError` for anything else so the caller never hits the API with
    a bad date (which the BOE would answer with an opaque 404).
    """
    if not isinstance(value, str):
        raise InvalidInputError("Date must be a string like '2023-01-02' or '20230102'.")
    raw = value.strip()
    if _DATE_COMPACT_RE.match(raw):
        compact = raw
    else:
        m = _DATE_ISO_RE.match(raw)
        if not m:
            raise InvalidInputError(
                f"Invalid date {value!r}. Use 'YYYY-MM-DD' or 'YYYYMMDD'."
            )
        compact = "".join(m.groups())
    try:
        datetime.strptime(compact, "%Y%m%d")
    except ValueError as exc:
        raise InvalidInputError(f"Invalid calendar date {value!r}.") from exc
    return compact


def validate_boe_id(value: str) -> str:
    """Validate a BOE identifier (e.g. ``BOE-A-2013-5940``), returning it upper-cased.

    Rejecting malformed ids here turns a confusing remote 400/404 into a clear local message.
    """
    if not isinstance(value, str):
        raise InvalidInputError("BOE id must be a string like 'BOE-A-2013-5940'.")
    candidate = value.strip().upper()
    if not _BOE_ID_RE.match(candidate):
        raise InvalidInputError(
            f"Invalid BOE id {value!r}. Expected the form 'BOE-A-2013-5940'."
        )
    return candidate


def strip_accents(text: str) -> str:
    """Lower-case and drop diacritics, for accent-insensitive name filtering."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def aux_table_to_list(data: Any, name_filter: str | None = None) -> list[dict[str, str]]:
    """Normalise a ``datos-auxiliares`` payload to ``[{"codigo", "texto"}, ...]``.

    These endpoints return ``data`` as a ``{code: name}`` mapping (not a list). An optional
    accent/case-insensitive substring ``name_filter`` keeps the result small for the model.
    """
    entries: list[dict[str, str]]
    if isinstance(data, dict):
        entries = [{"codigo": str(k), "texto": str(v)} for k, v in data.items()]
    elif isinstance(data, list):
        # Some tables may already be list-shaped (e.g. {codigo, texto} objects).
        entries = []
        for item in data:
            if isinstance(item, dict):
                code = item.get("codigo") or item.get("@codigo") or item.get("id")
                text = item.get("texto") or item.get("descripcion") or item.get("nombre")
                entries.append({"codigo": str(code), "texto": str(text)})
    else:
        entries = []

    if name_filter:
        needle = strip_accents(name_filter)
        entries = [e for e in entries if needle in strip_accents(e["texto"])]
    entries.sort(key=lambda e: strip_accents(e["texto"]))
    return entries


def _block_element_to_dict(bloque: etree._Element) -> dict[str, Any]:
    """Convert a ``<bloque>`` element (article/chapter) to a dict with its versions."""
    versions = []
    for version in bloque.findall("version"):
        paragraphs = [
            (p.text or "").strip()
            for p in version.findall("p")
            if (p.text or "").strip()
        ]
        versions.append(
            {
                "id_norma": version.get("id_norma"),
                "fecha_publicacion": version.get("fecha_publicacion"),
                "fecha_vigencia": version.get("fecha_vigencia"),
                "texto": "\n".join(paragraphs),
            }
        )
    return {
        "id": bloque.get("id"),
        "tipo": bloque.get("tipo"),
        "titulo": bloque.get("titulo"),
        "versiones": versions,
    }


def parse_block_xml(tree: etree._Element) -> dict[str, Any]:
    """Parse a single ``/texto/bloque/{id}`` response into a structured block dict."""
    bloque = tree.find(".//bloque")
    if bloque is None:
        raise InvalidInputError("Response contained no <bloque> element.")
    return _block_element_to_dict(bloque)


def parse_text_xml(tree: etree._Element) -> list[dict[str, Any]]:
    """Parse a full ``/texto`` response into an ordered list of block dicts."""
    return [_block_element_to_dict(b) for b in tree.findall(".//bloque")]
