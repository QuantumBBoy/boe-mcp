"""Reference-table lookups: departments, subject matters and legal ranges.

These translate human names ("Ministerio de Hacienda") into the codes the search tool needs.
The tables change rarely, so responses are cached.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..client import BoeClient
from ..models import RefTableEntry
from ..parsing import aux_table_to_list

_AUX = "/datos-auxiliares"


def register(mcp: FastMCP, client: BoeClient) -> None:
    async def _lookup(table: str, name_filter: str | None) -> list[RefTableEntry]:
        data = await client.get_json(f"{_AUX}/{table}", cache=True)
        return [RefTableEntry(**row) for row in aux_table_to_list(data, name_filter)]

    @mcp.tool(
        description=(
            "List BOE department codes (organism issuing a norm), optionally filtered by a "
            "case/accent-insensitive name substring. Use the returned code as department_code in "
            "search_legislation."
        )
    )
    async def lookup_departments(name_filter: str | None = None) -> list[RefTableEntry]:
        return await _lookup("departamentos", name_filter)

    @mcp.tool(
        description=(
            "List BOE subject-matter (materia) codes, optionally filtered by a case/accent-"
            "insensitive name substring. Use the returned code as matter_code in search_legislation."
        )
    )
    async def lookup_matters(name_filter: str | None = None) -> list[RefTableEntry]:
        return await _lookup("materias", name_filter)

    @mcp.tool(
        description=(
            "List BOE legal-range (rango) codes — Ley, Real Decreto, Orden, etc. — optionally "
            "filtered by name substring. Use the returned code as legal_range_code in "
            "search_legislation."
        )
    )
    async def lookup_legal_ranges(name_filter: str | None = None) -> list[RefTableEntry]:
        return await _lookup("rangos", name_filter)
