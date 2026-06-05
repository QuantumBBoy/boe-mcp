"""Pydantic output models for the BOE tools.

Models capture the fields the tools surface explicitly while allowing the BOE's richer payloads
to pass through (``extra="allow"``). Field names mirror the Spanish API where they map directly.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow")


class RefTableEntry(_Base):
    """A reference-table row: a code and its human-readable name."""

    codigo: str
    texto: str


class SumarioItem(_Base):
    """A single disposition in a BOE/BORME daily summary, flattened from the nested sections."""

    identificador: str
    titulo: str
    seccion: str | None = None
    departamento: str | None = None
    epigrafe: str | None = None
    url_pdf: str | None = None
    url_html: str | None = None
    url_xml: str | None = None


class SummaryResult(_Base):
    """Result of a daily-summary lookup."""

    fecha: str
    fecha_publicacion: str | None = None
    publicacion: str | None = None
    total_items: int
    items: list[SumarioItem] = Field(default_factory=list)


class NormaListItem(_Base):
    """A consolidated-legislation search hit (list-level metadata)."""

    identificador: str
    titulo: str | None = None
    fecha_actualizacion: str | None = None
    fecha_disposicion: str | None = None
    fecha_publicacion: str | None = None
    numero_oficial: str | None = None
    ambito: Any | None = None
    departamento: Any | None = None
    rango: Any | None = None
    vigencia_agotada: str | None = None
    estado_consolidacion: Any | None = None
    url_eli: str | None = None
    url_html_consolidada: str | None = None


class SearchResult(_Base):
    """Wrapper around a page of consolidated-legislation hits."""

    total: int
    offset: int
    limit: int
    results: list[NormaListItem] = Field(default_factory=list)


class TextBlockVersion(_Base):
    """One time-versioned rendering of a text block."""

    id_norma: str | None = None
    fecha_publicacion: str | None = None
    fecha_vigencia: str | None = None
    texto: str = ""


class TextBlock(_Base):
    """A consolidated-text block (article, chapter, preamble, …) with all its versions."""

    id: str | None = None
    tipo: str | None = None
    titulo: str | None = None
    versiones: list[TextBlockVersion] = Field(default_factory=list)


class IndexEntry(_Base):
    """An entry in a law's text index — a cheap pointer to one block."""

    id: str
    titulo: str = ""
    fecha_actualizacion: str | None = None


class LawMetadata(_Base):
    """Norm metadata (rank, dates, organ, vigencia, ELI link). Rich fields pass through."""

    identificador: str
    titulo: str | None = None


class Analisis(_Base):
    """Legal analysis: subject matters, notes, and references to/from other norms."""

    materias: list[Any] = Field(default_factory=list)
    notas: list[Any] = Field(default_factory=list)
    referencias: dict[str, Any] = Field(default_factory=dict)
