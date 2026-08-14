"""Contrato ChangeUnit — ver docs/arquitectura.md §2.1.

Congelado por diseño: cualquier cambio aquí debe regenerar
frontend/src/types/change_unit.ts en el mismo commit (invariante #5, CLAUDE.md).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BBox = tuple[float, float, float, float]
PageSize = tuple[float, float]

Kind = Literal["insert", "delete", "replace", "format", "visual", "move"]
Cuadrante = Literal["trivial", "parafrasis", "critico_oculto", "reescritura"]
Direccion = Literal["restrictivo", "permisivo", "equivalente", "divergente"]
Naturaleza = Literal[
    "obligacion",
    "plazo",
    "umbral",
    "alcance",
    "procedimiento",
    "definicion",
    "referencia",
    "sancion",
]
Severidad = Literal["alta", "media", "baja", "nula"]
Status = Literal["ok", "failed", "skipped", "stale"]
ReviewEstado = Literal["pendiente", "aceptado", "corregido", "descartado_fp"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Signals(_Strict):
    """Señales calculadas sin modelo generativo (§4, WP-6)."""

    delta_lexico: float | None = Field(default=None, ge=0.0)
    delta_semantico: float | None = Field(default=None, ge=0.0, le=1.0)
    cuadrante: Cuadrante | None = None
    lexico_critico: list[str] = Field(default_factory=list)
    elevacion_deterministica: bool = False
    # Clasificación de §4.4 (coma en cláusula relativa, enumeración, etc).
    # No se fija como Literal: el documento la deja abierta ("…").
    clase_puntuacion: str | None = None


class Evidencia(_Strict):
    """Spans literales que sustentan el análisis (§4.7 — grounding)."""

    span_a: str | None = None
    span_b: str | None = None


class Provenance(_Strict):
    provider: str
    model: str
    prompt_version: str
    temperature: float
    used_vision: bool
    input_hash: str
    timestamp: datetime
    latency_ms: int


class Analysis(_Strict):
    """Salida del rol analista_texto/analista_vision (§4, WP-6b)."""

    status: Status = "skipped"
    que_cambio: str | None = None
    implicacion: str | None = None
    direccion: Direccion | None = None
    naturaleza: Naturaleza | None = None
    efecto_esperado: str | None = None
    riesgo_si_no_se_atiende: str | None = None
    evidencia: Evidencia | None = None
    severidad: Severidad | None = None
    requiere_criterio_humano: bool = False
    motivo_abstencion: str | None = None
    confianza: float | None = Field(default=None, ge=0.0, le=1.0)
    provenance: Provenance | None = None


class Review(_Strict):
    """Estado de revisión humana (§6)."""

    estado: ReviewEstado = "pendiente"
    comentario: str | None = None
    interpretacion_corregida: str | None = None
    revisor: str | None = None
    revisado_en: datetime | None = None


class ChangeUnit(_Strict):
    """Unidad de todo el sistema — una fila de la tabla de revisión (§2.1)."""

    id: str
    run_id: str

    # --- Localización ---
    kind: Kind
    page_a: int | None = None
    page_b: int | None = None
    bbox_a: list[BBox] = Field(default_factory=list)
    bbox_b: list[BBox] = Field(default_factory=list)
    page_size_a: PageSize | None = None
    page_size_b: PageSize | None = None
    section_path: str = ""
    anchor_confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # --- Contenido ---
    text_a: str = ""
    text_b: str = ""
    context_a: str = ""
    context_b: str = ""

    # --- Señales calculadas / análisis / revisión ---
    signals: Signals = Field(default_factory=Signals)
    analysis: Analysis = Field(default_factory=Analysis)
    review: Review = Field(default_factory=Review)

    # --- Salida final al papel de trabajo (§6, WP-8) ---
    calificacion_analisis: str | None = None
