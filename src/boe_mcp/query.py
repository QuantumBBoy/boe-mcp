"""Builder for the consolidated-legislation search ``query`` parameter.

The ``/legislacion-consolidada`` endpoint takes a JSON search document of the shape::

    {"query": {"query_string": {"query": "campo:valor and ..."},
               "range": {"fecha_publicacion": {"gte": "...", "lte": "..."}}},
     "sort": [...]}

This module turns the friendly tool inputs into that document so callers never hand-write the DSL.
"""

from __future__ import annotations

import json
from typing import Any

from .parsing import normalise_date

# Characters with special meaning in the Lucene-style query_string syntax.
_RESERVED = r'+-=&|><!(){}[]^"~*?:\/'


def escape_value(value: str) -> str:
    """Escape reserved characters and wrap multi-word values in quotes for query_string."""
    text = value.strip()
    escaped = "".join("\\" + c if c in _RESERVED else c for c in text)
    if " " in escaped:
        return f'"{escaped}"'
    return escaped


def build_search_query(
    *,
    text: str | None = None,
    department_code: str | None = None,
    legal_range_code: str | None = None,
    matter_code: str | None = None,
    scope_code: str | None = None,
    published_from: str | None = None,
    published_to: str | None = None,
    include_repealed: bool = False,
    sort: str | None = None,
) -> str:
    """Return the JSON-encoded ``query`` document for the given filters.

    ``text`` is matched against both ``titulo`` and ``texto`` (full text). Code filters map to the
    documented ``campo@codigo`` fields. ``published_from``/``published_to`` become a range on
    ``fecha_publicacion``. ``include_repealed=False`` constrains ``vigencia_agotada`` to active norms.
    """
    clauses: list[str] = []

    if text:
        value = escape_value(text)
        clauses.append(f"(titulo:{value} or texto:{value})")
    if department_code:
        clauses.append(f"departamento@codigo:{escape_value(department_code)}")
    if legal_range_code:
        clauses.append(f"rango@codigo:{escape_value(legal_range_code)}")
    if matter_code:
        clauses.append(f"materia@codigo:{escape_value(matter_code)}")
    if scope_code:
        clauses.append(f"ambito@codigo:{escape_value(scope_code)}")
    if not include_repealed:
        # vigencia_agotada is "S" for spent/repealed norms; "N" keeps active ones.
        clauses.append("vigencia_agotada:N")

    query_inner: dict[str, Any] = {}
    if clauses:
        query_inner["query_string"] = {"query": " and ".join(clauses)}

    if published_from or published_to:
        bounds: dict[str, str] = {}
        if published_from:
            bounds["gte"] = normalise_date(published_from)
        if published_to:
            bounds["lte"] = normalise_date(published_to)
        query_inner["range"] = {"fecha_publicacion": bounds}

    document: dict[str, Any] = {"query": query_inner}
    if sort:
        # Accept either "field" or "field:asc"/"field:desc".
        field, _, direction = sort.partition(":")
        document["sort"] = [{field: {"order": direction or "asc"}}]

    return json.dumps(document, ensure_ascii=False)
