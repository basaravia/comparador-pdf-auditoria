"""ChangeUnit es el contrato central (§2.1). Estos tests fijan su forma."""

import json
from pathlib import Path

from comparador.schemas import ChangeUnit

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORTED_SCHEMA_PATH = REPO_ROOT / "schemas" / "change_unit.schema.json"


def test_minimal_change_unit_uses_sensible_defaults():
    cu = ChangeUnit(id="cu_0001", run_id="run_test", kind="insert")

    assert cu.review.estado == "pendiente"
    assert cu.analysis.status == "skipped"
    assert cu.signals.elevacion_deterministica is False
    assert cu.bbox_a == []
    assert cu.anchor_confidence == 1.0


def test_full_example_from_design_doc_validates():
    cu = ChangeUnit(
        id="cu_0031",
        run_id="run_a91f",
        kind="replace",
        page_a=12,
        page_b=12,
        bbox_a=[(72.0, 310.5, 468.2, 322.1)],
        bbox_b=[(72.0, 310.5, 481.7, 334.8)],
        page_size_a=(595.3, 841.9),
        page_size_b=(595.3, 841.9),
        section_path="Título II > Capítulo 3 > Art. 35",
        anchor_confidence=0.94,
        text_a="el plazo será de treinta (30) días",
        text_b="el plazo será de quince (15) días hábiles",
        context_a="…párrafo completo con el fragmento marcado con «del»…",
        context_b="…párrafo completo con el fragmento marcado con «ins»…",
        signals={
            "delta_lexico": 0.18,
            "delta_semantico": 0.71,
            "cuadrante": "critico_oculto",
            "lexico_critico": ["temporal", "umbral"],
            "elevacion_deterministica": True,
        },
        analysis={
            "status": "ok",
            "que_cambio": "Reducción del plazo de 30 a 15 días, ahora hábiles.",
            "direccion": "restrictivo",
            "naturaleza": "plazo",
            "severidad": "alta",
            "confianza": 0.86,
            "evidencia": {"span_a": "treinta (30) días", "span_b": "quince (15) días hábiles"},
            "provenance": {
                "provider": "dmr",
                "model": "qwen3-vl:8b",
                "prompt_version": "analisis_v3",
                "temperature": 0.0,
                "used_vision": False,
                "input_hash": "sha256:deadbeef",
                "timestamp": "2026-08-14T15:02:11Z",
                "latency_ms": 2840,
            },
        },
    )

    assert cu.signals.cuadrante == "critico_oculto"
    assert cu.analysis.direccion == "restrictivo"
    assert cu.analysis.provenance.provider == "dmr"


def test_extra_fields_are_rejected():
    """El esquema está congelado (§2): un campo inventado debe fallar, no ignorarse."""
    from pydantic import ValidationError

    try:
        ChangeUnit(id="cu_1", run_id="run_1", kind="insert", campo_inventado=True)
    except ValidationError:
        return
    raise AssertionError("se esperaba ValidationError por campo no declarado")


def test_exported_json_schema_matches_current_model():
    """Invariante #5: todo cambio al modelo regenera schemas/change_unit.schema.json."""
    assert EXPORTED_SCHEMA_PATH.exists(), (
        "falta schemas/change_unit.schema.json — correr "
        "`uv run python -m comparador.schemas.export`"
    )
    on_disk = json.loads(EXPORTED_SCHEMA_PATH.read_text())
    current = ChangeUnit.model_json_schema()
    current["title"] = "ChangeUnit"
    assert on_disk == current, (
        "schemas/change_unit.schema.json está desactualizado respecto al modelo — correr "
        "`uv run python -m comparador.schemas.export` y regenerar los tipos TS"
    )
