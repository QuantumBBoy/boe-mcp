# BOE MCP Server

[![CI](https://github.com/QuantumBBoy/boe-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/QuantumBBoy/boe-mcp/actions/workflows/ci.yml)

An [MCP](https://modelcontextprotocol.io) server for Spain's **Boletín Oficial del Estado (BOE)**.
It lets an LLM query the official state gazette and consolidated legislation in natural language —
no PDFs, no wrestling with the BOE web search.

It wraps the public [BOE open-data API](https://www.boe.es/datosabiertos/api/api.php):

- **Daily gazettes** — what was published in the BOE/BORME on a given date.
- **Consolidated legislation** — search laws by department, legal range, subject matter, scope and
  date; retrieve a norm's metadata, legal analysis (subject matters, notes, references to other
  norms), structure (text index) and the text of a single article block.
- **Reference tables** — resolve department / subject-matter / legal-range names into the codes the
  search needs.

> **What is the BOE?** The *Boletín Oficial del Estado* is Spain's official journal, where laws and
> official acts are published. The **BORME** is its commercial-registry counterpart. *Consolidated
> legislation* is the up-to-date, amended text of a norm assembled by the BOE.

> ⚖️ **Attribution is mandatory (not optional).** Any reuse of this data **must** display the line
> **«Fuente de los datos: Agencia Estatal Boletín Oficial del Estado»** and **preserve the update
> date** (`fecha_actualizacion`) returned with each norm. **Consolidated texts have no official
> legal value** — only the BOE edition published in the gazette is authentic. See
> [Attribution & legal](#attribution--legal).

## Install

Requires Python ≥ 3.10. Run straight from the source tree with [uv](https://docs.astral.sh/uv/):

```bash
uv run boe-mcp          # or: pip install -e . && boe-mcp
```

### Claude Desktop

Add to `claude_desktop_config.json` (see [`examples/`](examples/claude_desktop_config.json)):

```json
{
  "mcpServers": {
    "boe": { "command": "uvx", "args": ["boe-mcp"] }
  }
}
```

### MCP Inspector

```bash
uv run mcp dev src/boe_mcp/server.py
```

## Tools

| Tool | What it does |
|------|--------------|
| `get_boe_summary(date, section_filter?, max_items?)` | BOE daily summary, flattened to items (identifier, title, section, department, URLs). |
| `get_borme_summary(date, …)` | Same, for the commercial-registry gazette (BORME). |
| `search_legislation(text?, department_code?, legal_range_code?, matter_code?, scope_code?, from_date?, to_date?, published_from?, published_to?, include_repealed?, offset?, limit?, sort?)` | Search consolidated legislation; returns norm metadata. |
| `get_law(law_id, include_text?)` | A norm's metadata; with `include_text=true`, also the full consolidated text as blocks. |
| `get_law_metadata(law_id)` | Lightweight metadata (rank, dates, organ, vigencia/derogation, ELI link). |
| `get_law_analysis(law_id)` | Subject matters, notes, and references (anteriores/posteriores) to/from other norms. |
| `get_law_index(law_id)` | Ordered list of `{id, titulo}` text blocks — a cheap index. |
| `get_law_block(law_id, block_id)` | One block (e.g. a single article) with version annotations. |
| `lookup_departments(name_filter?)` | Department code↔name table. |
| `lookup_matters(name_filter?)` | Subject-matter code↔name table. |
| `lookup_legal_ranges(name_filter?)` | Legal-range code↔name table (Ley, Real Decreto, …). |

Dates accept `YYYY-MM-DD` or `YYYYMMDD`. Identifiers look like `BOE-A-2013-5940`.

### Resources

- `boe://summary/{date}` — daily summary by date.
- `boe://law/{law_id}` — consolidated norm metadata.
- `boe://reference/departments`, `boe://reference/matters`, `boe://reference/legal-ranges` — cached
  lookup tables.

### Prompts

`summarize_boe_day(date)`, `analyze_law(law_id)`, `compare_laws(id_a, id_b)`,
`search_and_summarize(topic)`.

## The search query DSL

`search_legislation` builds the BOE's JSON `query` document for you. Inputs map to fields as:

| Input | BOE field |
|-------|-----------|
| `text` | `titulo` **and** `texto` (full text) |
| `department_code` | `departamento@codigo` |
| `legal_range_code` | `rango@codigo` |
| `matter_code` | `materia@codigo` |
| `scope_code` | `ambito@codigo` |
| `published_from` / `published_to` | range on `fecha_publicacion` |
| `from_date` / `to_date` | last-update window (`from` / `to`) |
| `include_repealed=false` | constrains `vigencia_agotada` to active norms |

For example, `search_legislation(text="crisis", legal_range_code="1300", published_from="2019-01-01")`
produces `(titulo:crisis or texto:crisis) and rango@codigo:1300 and vigencia_agotada:N` with a
`fecha_publicacion >= 20190101` range. Resolve codes with the `lookup_*` tools first.

## Attribution & legal

Reuse of BOE data is governed by the
[BOE reuse conditions](https://www.boe.es/avisos_legales/reutilizacion.php) (license type approved
by Resolution of 27 June 2024). Using this server implies acceptance of those conditions. They are
**requirements, not suggestions:**

- **Attribution is mandatory.** Display, verbatim, the source line:

  > Fuente de los datos: Agencia Estatal Boletín Oficial del Estado

- **Preserve the update date.** The `fecha_actualizacion` (and reuse-condition metadata) returned
  with each norm/summary must be kept — do not strip it.
- **Consolidated texts have no official legal value.** Only the edition **published in the BOE
  gazette is authentic**; consolidated text is informative.
- The BOE may **suspend access** to anyone breaching these conditions, so the server self-throttles
  and caches.

### Other notes

- The **BORME** contains personal/company data subject to GDPR (Reglamento (UE) 2016/679 and
  LO 3/2018); handle accordingly.
- All data are in Spanish (some BOE content in co-official languages). Source text is returned
  faithfully; ask the model to translate or summarise.
- Dates with no gazette (some Sundays/holidays) legitimately return "not found".

## Development

```bash
uv pip install -e ".[dev]"
uv run pytest          # offline tests with recorded HTTP fixtures (respx)
uv run ruff check
```

Tested with `mcp` 1.27, `httpx` 0.27+, `lxml` 6, `pydantic` 2, Python 3.12.

## License

MIT (code) — see [LICENSE](LICENSE). BOE data is subject to the BOE reuse conditions above.
