"""Consolidated-legislation tools: search, metadata, analysis, index and text blocks."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from ..client import BoeClient, BoeNotFoundError, BoeValidationError
from ..models import (
    Analisis,
    IndexEntry,
    LawMetadata,
    NormaListItem,
    SearchResult,
    TextBlock,
)
from ..parsing import (
    InvalidInputError,
    normalise_date,
    parse_block_xml,
    parse_text_xml,
    validate_boe_id,
)
from ..query import build_search_query

_LEG = "/legislacion-consolidada"


def _first(data: Any) -> dict[str, Any]:
    """Unwrap the single-element list the metadata-style endpoints return."""
    if isinstance(data, list):
        return data[0] if data else {}
    return data if isinstance(data, dict) else {}


def register(mcp: FastMCP, client: BoeClient) -> None:
    @mcp.tool(
        description=(
            "Search consolidated Spanish legislation. Filter by free text (title/full-text), "
            "department/legal-range/subject-matter/scope codes (use the lookup_* tools to resolve "
            "names to codes), publication-date range, and last-update window. Returns norm metadata "
            "(identifier, title, dates, rank, department, ELI link). Repealed norms are excluded "
            "unless include_repealed=true."
        )
    )
    async def search_legislation(
        text: str | None = None,
        department_code: str | None = None,
        legal_range_code: str | None = None,
        matter_code: str | None = None,
        scope_code: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        published_from: str | None = None,
        published_to: str | None = None,
        include_repealed: bool = False,
        offset: int = 0,
        limit: int = 25,
        sort: str | None = None,
    ) -> SearchResult:
        try:
            query = build_search_query(
                text=text,
                department_code=department_code,
                legal_range_code=legal_range_code,
                matter_code=matter_code,
                scope_code=scope_code,
                published_from=published_from,
                published_to=published_to,
                include_repealed=include_repealed,
                sort=sort,
            )
            params: dict[str, Any] = {"query": query, "offset": offset, "limit": limit}
            if from_date:
                params["from"] = normalise_date(from_date)
            if to_date:
                params["to"] = normalise_date(to_date)
        except InvalidInputError as exc:
            raise ToolError(str(exc)) from exc

        try:
            data = await client.get_json(_LEG, params=params)
        except BoeValidationError as exc:
            raise ToolError(f"The BOE rejected this search (check codes/dates): {exc}") from exc

        rows = data if isinstance(data, list) else []
        results = [NormaListItem(**row) for row in rows if isinstance(row, dict)]
        return SearchResult(total=len(results), offset=offset, limit=limit, results=results)

    @mcp.tool(
        description=(
            "Get the metadata of a consolidated norm (rank, dates, organ, vigencia/derogation "
            "status, ELI link) without loading its text. law_id like 'BOE-A-2013-5940'."
        )
    )
    async def get_law_metadata(law_id: str) -> LawMetadata:
        norm_id = _validate(law_id)
        data = await _get(client, f"{_LEG}/id/{norm_id}/metadatos", norm_id)
        return LawMetadata(**_first(data))

    @mcp.tool(
        description=(
            "Get the legal analysis of a norm: subject matters (materias), notes (notas), and "
            "references to/from other norms (referencias: anteriores/posteriores with relation "
            "type and target id) — i.e. what it modifies or derogates and what later affects it."
        )
    )
    async def get_law_analysis(law_id: str) -> Analisis:
        norm_id = _validate(law_id)
        data = await _get(client, f"{_LEG}/id/{norm_id}/analisis", norm_id)
        first = _first(data)
        return Analisis(
            materias=first.get("materias", []) or [],
            notas=first.get("notas", []) or [],
            referencias=first.get("referencias", {}) or {},
        )

    @mcp.tool(
        description=(
            "Get the ordered index of a norm's consolidated text — a cheap list of {id, titulo} "
            "blocks (preamble, chapters, articles, annexes). Use a block id with get_law_block."
        )
    )
    async def get_law_index(law_id: str) -> list[IndexEntry]:
        norm_id = _validate(law_id)
        data = await _get(client, f"{_LEG}/id/{norm_id}/texto/indice", norm_id)
        blocks = _first(data).get("bloque", [])
        blocks = blocks if isinstance(blocks, list) else [blocks]
        return [
            IndexEntry(
                id=b.get("id", ""),
                titulo=b.get("titulo", ""),
                fecha_actualizacion=b.get("fecha_actualizacion"),
            )
            for b in blocks
            if isinstance(b, dict)
        ]

    @mcp.tool(
        description=(
            "Get a single block of a norm's consolidated text (e.g. one article) by its block id "
            "from get_law_index. Returns the block text with version annotations. XML-only endpoint."
        )
    )
    async def get_law_block(law_id: str, block_id: str) -> TextBlock:
        norm_id = _validate(law_id)
        if not block_id or not block_id.strip():
            raise ToolError("block_id is required (get one from get_law_index).")
        path = f"{_LEG}/id/{norm_id}/texto/bloque/{block_id.strip()}"
        try:
            tree = await client.get_xml(path)
        except BoeNotFoundError as exc:
            raise ToolError(f"No block {block_id!r} in norm {norm_id}.") from exc
        try:
            return TextBlock(**parse_block_xml(tree))
        except InvalidInputError as exc:
            raise ToolError(str(exc)) from exc

    @mcp.tool(
        description=(
            "Get a consolidated norm. Returns its metadata; if include_text=true also returns the "
            "full consolidated text as ordered, version-annotated blocks (larger response)."
        )
    )
    async def get_law(law_id: str, include_text: bool = False) -> dict[str, Any]:
        norm_id = _validate(law_id)
        data = await _get(client, f"{_LEG}/id/{norm_id}/metadatos", norm_id)
        result: dict[str, Any] = {"metadata": LawMetadata(**_first(data)).model_dump()}
        if include_text:
            tree = await client.get_xml(f"{_LEG}/id/{norm_id}/texto")
            result["bloques"] = [TextBlock(**b).model_dump() for b in parse_text_xml(tree)]
        return result


def _validate(law_id: str) -> str:
    try:
        return validate_boe_id(law_id)
    except InvalidInputError as exc:
        raise ToolError(str(exc)) from exc


async def _get(client: BoeClient, path: str, norm_id: str) -> Any:
    try:
        return await client.get_json(path)
    except BoeNotFoundError as exc:
        raise ToolError(f"No consolidated norm found for {norm_id}.") from exc
