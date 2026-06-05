"""BOE MCP server: FastMCP instance, registration and entry point.

Exposes Spain's Boletín Oficial del Estado (BOE/BORME daily gazettes and consolidated legislation)
over the Model Context Protocol, plus reference-table lookups, resource templates and prompts.

Data source: Agencia Estatal Boletín Oficial del Estado (https://www.boe.es/datosabiertos/).
Consolidated texts have no official legal value; only the published BOE edition is authentic.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .client import BoeClient, BoeError
from .models import LawMetadata
from .parsing import aux_table_to_list, normalise_date, validate_boe_id
from .tools import auxiliary, legislation, summaries
from .tools.legislation import _first
from .tools.summaries import flatten_summary

INSTRUCTIONS = (
    "Query Spain's Official State Gazette (BOE/BORME) and consolidated legislation. "
    "Resolve names to codes with lookup_departments/lookup_matters/lookup_legal_ranges before "
    "searching. Field names are Spanish. Attribution: 'Fuente de los datos: Agencia Estatal "
    "Boletín Oficial del Estado'. Consolidated texts have no official legal value."
)

mcp = FastMCP("boe-mcp", instructions=INSTRUCTIONS, website_url="https://www.boe.es/datosabiertos/")
client = BoeClient()

# --- Tools ---------------------------------------------------------------------------------------
summaries.register(mcp, client)
legislation.register(mcp, client)
auxiliary.register(mcp, client)


# --- Resources -----------------------------------------------------------------------------------
def _dump(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


@mcp.resource("boe://summary/{date}", mime_type="application/json")
async def summary_resource(date: str) -> str:
    """BOE daily summary for a date (YYYY-MM-DD or YYYYMMDD)."""
    fecha = normalise_date(date)
    data = await client.get_json(f"/boe/sumario/{fecha}")
    return _dump(flatten_summary(data, fecha, None, None).model_dump())


@mcp.resource("boe://law/{law_id}", mime_type="application/json")
async def law_resource(law_id: str) -> str:
    """Consolidated norm metadata for a BOE identifier."""
    norm_id = validate_boe_id(law_id)
    data = await client.get_json(f"/legislacion-consolidada/id/{norm_id}/metadatos")
    return _dump(LawMetadata(**_first(data)).model_dump())


async def _reference(table: str) -> str:
    data = await client.get_json(f"/datos-auxiliares/{table}", cache=True)
    return _dump(aux_table_to_list(data))


@mcp.resource("boe://reference/departments", mime_type="application/json")
async def departments_resource() -> str:
    """Cached department code↔name table."""
    return await _reference("departamentos")


@mcp.resource("boe://reference/matters", mime_type="application/json")
async def matters_resource() -> str:
    """Cached subject-matter code↔name table."""
    return await _reference("materias")


@mcp.resource("boe://reference/legal-ranges", mime_type="application/json")
async def legal_ranges_resource() -> str:
    """Cached legal-range code↔name table."""
    return await _reference("rangos")


# --- Prompts -------------------------------------------------------------------------------------
@mcp.prompt(description="Summarise the most relevant dispositions published in the BOE on a date.")
def summarize_boe_day(date: str) -> str:
    return (
        f"Use get_boe_summary for {date}. Produce a concise digest in the user's language, grouping "
        "the most relevant dispositions by section and department. For each highlight, give the "
        "identifier, a one-line plain-language summary, and the HTML/PDF link. Note if no gazette "
        "was published that day. Close with: 'Fuente de los datos: Agencia Estatal Boletín Oficial "
        "del Estado.'"
    )


@mcp.prompt(description="Analyse a consolidated law: metadata, vigencia, structure and relations.")
def analyze_law(law_id: str) -> str:
    return (
        f"Analyse the consolidated norm {law_id}. Call get_law_metadata (rank, dates, organ, "
        "vigencia/derogation, ELI), get_law_analysis (materias, notas, references to/from other "
        "norms), and get_law_index (structure). Summarise what the norm does, whether it is in "
        "force, what it modifies or derogates, and which later norms affect it. Remind the user "
        "the consolidated text has no official legal value."
    )


@mcp.prompt(description="Compare two laws and identify modification/derogation relations between them.")
def compare_laws(id_a: str, id_b: str) -> str:
    return (
        f"Compare consolidated norms {id_a} and {id_b}. Fetch get_law_metadata and get_law_analysis "
        "for both. Determine whether one modifies, derogates or otherwise references the other "
        "(inspect referencias anteriores/posteriores), and summarise their relationship and the "
        "current vigencia of each."
    )


@mcp.prompt(description="Search consolidated legislation on a topic and summarise the top hits.")
def search_and_summarize(topic: str) -> str:
    return (
        f"Find consolidated legislation about: {topic}. If helpful, resolve relevant department/"
        "matter/range names to codes with the lookup_* tools, then call search_legislation. "
        "Summarise the top hits with identifier, title, rank, publication date and ELI link, and "
        "offer to retrieve the text of any of them. Close with the BOE attribution line."
    )


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    try:
        mcp.run("stdio")
    except BoeError:  # pragma: no cover - defensive; per-tool errors are surfaced as ToolError
        raise


if __name__ == "__main__":
    main()
