"""Daily-summary tools: BOE and BORME gazettes for a given date."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from ..client import BoeClient, BoeNotFoundError
from ..models import SumarioItem, SummaryResult
from ..parsing import InvalidInputError, normalise_date


def _as_list(value: Any) -> list[Any]:
    """Coerce a BOE field to a list (the API emits single dicts for singletons)."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _url_text(value: Any) -> str | None:
    """Extract a URL: ``url_html``/``url_xml`` are strings, ``url_pdf`` is a dict with ``texto``."""
    if isinstance(value, dict):
        return value.get("texto")
    if isinstance(value, str):
        return value
    return None


def flatten_summary(data: Any, fecha: str, section_filter: str | None, max_items: int | None) -> SummaryResult:
    """Flatten the nested sections→departments→epígrafes→items tree into a flat item list."""
    sumario = data.get("sumario", {}) if isinstance(data, dict) else {}
    metadatos = sumario.get("metadatos", {}) if isinstance(sumario, dict) else {}

    items: list[SumarioItem] = []
    for diario in _as_list(sumario.get("diario")):
        for seccion in _as_list(diario.get("seccion")):
            sec_name = seccion.get("nombre")
            if section_filter and section_filter.lower() not in (sec_name or "").lower():
                if section_filter.lower() != (seccion.get("codigo") or "").lower():
                    continue
            for dep in _as_list(seccion.get("departamento")):
                dep_name = dep.get("nombre")
                # Items live under epígrafes, or directly on the department.
                leaf_groups = _as_list(dep.get("epigrafe")) or [dep]
                for group in leaf_groups:
                    epigrafe_name = group.get("nombre") if group is not dep else None
                    for item in _as_list(group.get("item")):
                        items.append(
                            SumarioItem(
                                identificador=item.get("identificador", ""),
                                titulo=item.get("titulo", ""),
                                seccion=sec_name,
                                departamento=dep_name,
                                epigrafe=epigrafe_name,
                                url_pdf=_url_text(item.get("url_pdf")),
                                url_html=_url_text(item.get("url_html")),
                                url_xml=_url_text(item.get("url_xml")),
                            )
                        )

    total = len(items)
    if max_items is not None and max_items >= 0:
        items = items[:max_items]
    return SummaryResult(
        fecha=fecha,
        fecha_publicacion=metadatos.get("fecha_publicacion"),
        publicacion=metadatos.get("publicacion"),
        total_items=total,
        items=items,
    )


def register(mcp: FastMCP, client: BoeClient) -> None:
    async def _summary(kind: str, date: str, section_filter: str | None, max_items: int | None) -> SummaryResult:
        try:
            fecha = normalise_date(date)
        except InvalidInputError as exc:
            raise ToolError(str(exc)) from exc
        try:
            data = await client.get_json(f"/{kind}/sumario/{fecha}")
        except BoeNotFoundError as exc:
            raise ToolError(
                f"No {kind.upper()} was published on {date} (some Sundays/holidays have no gazette)."
            ) from exc
        return flatten_summary(data, fecha, section_filter, max_items)

    @mcp.tool(
        description=(
            "Get the BOE (Boletín Oficial del Estado) daily summary for a date. Returns the "
            "published dispositions flattened to identifier, title, section, department and URLs. "
            "Date may be YYYY-MM-DD or YYYYMMDD."
        )
    )
    async def get_boe_summary(
        date: str, section_filter: str | None = None, max_items: int | None = None
    ) -> SummaryResult:
        return await _summary("boe", date, section_filter, max_items)

    @mcp.tool(
        description=(
            "Get the BORME (commercial registry gazette) daily summary for a date. Same shape as "
            "the BOE summary. Date may be YYYY-MM-DD or YYYYMMDD."
        )
    )
    async def get_borme_summary(
        date: str, section_filter: str | None = None, max_items: int | None = None
    ) -> SummaryResult:
        return await _summary("borme", date, section_filter, max_items)
