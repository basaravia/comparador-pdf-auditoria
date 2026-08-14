"""Generador de PDFs sintéticos para el corpus dorado de fixtures (WP-0, §8).

Produce pares de PDF (A = "anterior", B = "vigente"), cada uno con exactamente
un tipo de cambio conocido, más `ground_truth.json` describiendo cada cambio
plantado. Es el ground truth contra el que WP-2 mide precisión/recall del
motor de diff y WP-6 mide recall de léxico crítico (docs/arquitectura.md §8, §9b).

El texto es sintético y normativo-ficticio: no representa ninguna norma real.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "generated"

_styles = getSampleStyleSheet()
_TITLE = ParagraphStyle("TituloNorma", parent=_styles["Heading1"], fontSize=14, spaceAfter=14)
_HEADING = ParagraphStyle(
    "TituloSeccion", parent=_styles["Heading2"], fontSize=12, spaceBefore=6, spaceAfter=10
)
_BODY = ParagraphStyle("Cuerpo", parent=_styles["Normal"], fontSize=10, leading=15, spaceAfter=10)

_KIND_STYLE = {"title": _TITLE, "heading": _HEADING, "body": _BODY}


@dataclass(frozen=True)
class Block:
    kind: str  # "title" | "heading" | "body"
    text: str


@dataclass(frozen=True)
class GroundTruthEntry:
    case_id: str
    categoria: str
    kind: str  # insert | delete | replace | format | move
    lexico_critico: list[str]
    direccion_esperada: str | None  # restrictivo | permisivo | equivalente | divergente
    text_a: str | None
    text_b: str | None
    nota: str


BASE_TITLE = "NORMA DE PRUEBA — GESTIÓN DE RIESGOS (FIXTURE SINTÉTICO, NO OFICIAL)"

ART_30 = (
    "Art. 30. Plazo de respuesta. El sujeto obligado deberá responder la solicitud del "
    "usuario en un plazo de treinta (30) días calendario, contados a partir de la fecha "
    "de recepción."
)
ART_31 = (
    "Art. 31. Notificación. La entidad notificará al interesado y al ente regulador "
    "dentro de los cinco (5) días siguientes a la resolución."
)
ART_32 = (
    "Art. 32. Alcance. Esta norma aplica a todas las instituciones financieras que "
    "operen en el territorio nacional."
)
ART_33 = (
    "Art. 33. Excepciones. No se aplicará esta disposición a las cooperativas de ahorro "
    "y crédito de nivel 1."
)
ART_34 = (
    "Art. 34. Sanciones. Los bancos que incumplan esta disposición serán sancionados "
    "conforme al régimen disciplinario vigente."
)
ART_35 = (
    "Art. 35. Disposición transitoria. Las entidades constituidas antes de la vigencia "
    "de esta norma contarán con un plazo de ciento ochenta (180) días para adecuar sus "
    "procesos internos a lo aquí dispuesto, sin perjuicio de las obligaciones de reporte "
    "que ya se encuentren vigentes."
)
ART_36 = (
    "Art. 36. Vigencia. La presente norma entrará en vigencia a partir de su publicación "
    "en el registro oficial y deroga cualquier disposición que le sea contraria."
)
ART_37 = (
    "Art. 37. Glosario. Para efectos de esta norma, se entenderá por «entidad "
    "supervisada» cualquier institución sujeta a la supervisión del ente regulador "
    "conforme a la ley."
)
ART_38 = (
    "Art. 38. Referencias. Esta norma debe interpretarse en conjunto con el Art. 12 y el "
    "Art. 45 del reglamento general, así como con las disposiciones del Anexo III."
)


def _base_blocks() -> list[Block]:
    return [
        Block("title", BASE_TITLE),
        Block("heading", "Título I — Disposiciones generales"),
        Block("body", ART_30),
        Block("body", ART_31),
        Block("body", ART_32),
        Block("heading", "Título II — Excepciones y sanciones"),
        Block("body", ART_33),
        Block("body", ART_34),
        Block("heading", "Título III — Disposiciones finales"),
        Block("body", ART_35),
        Block("body", ART_36),
        Block("body", ART_37),
        Block("body", ART_38),
    ]


def _index_containing(blocks: list[Block], needle: str) -> int:
    matches = [i for i, b in enumerate(blocks) if needle in b.text]
    if len(matches) != 1:
        raise ValueError(f"esperaba 1 bloque con {needle!r}, encontré {len(matches)}")
    return matches[0]


def _replace_once(blocks: list[Block], old: str, new: str) -> list[Block]:
    blocks = list(blocks)
    i = _index_containing(blocks, old)
    blocks[i] = replace(blocks[i], text=blocks[i].text.replace(old, new))
    return blocks


def _build_pdf(path: Path, blocks: list[Block]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    story = [Paragraph(b.text, _KIND_STYLE[b.kind]) for b in blocks]
    doc.build(story)


@dataclass(frozen=True)
class Case:
    case_id: str
    categoria: str
    kind: str
    lexico_critico: list[str]
    direccion_esperada: str | None
    nota: str
    build_b: Callable[[list[Block]], list[Block]]
    text_a: str | None
    text_b: str | None


def _cases() -> list[Case]:
    return [
        Case(
            case_id="temporal",
            categoria="temporal",
            kind="replace",
            lexico_critico=["temporal"],
            direccion_esperada="restrictivo",
            nota="Reduce el plazo de 30 a 15 días y lo pasa de calendario a hábiles.",
            build_b=lambda b: _replace_once(
                b, "treinta (30) días calendario", "quince (15) días hábiles"
            ),
            text_a="treinta (30) días calendario",
            text_b="quince (15) días hábiles",
        ),
        Case(
            case_id="deontico",
            categoria="deontico",
            kind="replace",
            lexico_critico=["deontico"],
            direccion_esperada="permisivo",
            nota="Convierte una obligación ('deberá') en una facultad ('podrá').",
            build_b=lambda b: _replace_once(b, "deberá responder", "podrá responder"),
            text_a="deberá responder",
            text_b="podrá responder",
        ),
        Case(
            case_id="conjuncion",
            categoria="conjuncion_logica",
            kind="replace",
            lexico_critico=["conjuncion_logica"],
            direccion_esperada="permisivo",
            nota="Cambia un requisito acumulativo ('y') por uno alternativo ('o').",
            build_b=lambda b: _replace_once(
                b, "al interesado y al ente regulador", "al interesado o al ente regulador"
            ),
            text_a="al interesado y al ente regulador",
            text_b="al interesado o al ente regulador",
        ),
        Case(
            case_id="parafrasis",
            categoria="parafrasis",
            kind="replace",
            lexico_critico=[],
            direccion_esperada="equivalente",
            nota="Léxico alto, semántico bajo: reescritura editorial sin cambio de sentido.",
            build_b=lambda b: _replace_once(
                b,
                "Esta norma aplica a todas las instituciones financieras que operen en el "
                "territorio nacional.",
                "Todas las instituciones financieras con operaciones en el país quedan "
                "sujetas a lo dispuesto en esta norma.",
            ),
            text_a=(
                "Esta norma aplica a todas las instituciones financieras que operen en el "
                "territorio nacional."
            ),
            text_b=(
                "Todas las instituciones financieras con operaciones en el país quedan "
                "sujetas a lo dispuesto en esta norma."
            ),
        ),
        Case(
            case_id="reescritura",
            categoria="reescritura",
            kind="replace",
            lexico_critico=["alcance", "umbral"],
            direccion_esperada="divergente",
            nota="Léxico alto, semántico alto: amplía el universo exceptuado y añade condición.",
            build_b=lambda b: _replace_once(
                b,
                "No se aplicará esta disposición a las cooperativas de ahorro y crédito de "
                "nivel 1.",
                "Las cooperativas de ahorro y crédito de nivel 1 y nivel 2 quedan "
                "exceptuadas de esta disposición, salvo que superen el umbral de activos "
                "establecido en el Anexo III.",
            ),
            text_a=(
                "No se aplicará esta disposición a las cooperativas de ahorro y crédito de "
                "nivel 1."
            ),
            text_b=(
                "Las cooperativas de ahorro y crédito de nivel 1 y nivel 2 quedan "
                "exceptuadas de esta disposición, salvo que superen el umbral de activos "
                "establecido en el Anexo III."
            ),
        ),
        Case(
            case_id="puntuacion",
            categoria="puntuacion_clausula_relativa",
            kind="replace",
            lexico_critico=[],
            direccion_esperada="divergente",
            nota=(
                "Dos comas convierten una cláusula especificativa (subconjunto de bancos) "
                "en explicativa (todos los bancos)."
            ),
            build_b=lambda b: _replace_once(
                b,
                "Los bancos que incumplan esta disposición serán sancionados",
                "Los bancos, que incumplan esta disposición, serán sancionados",
            ),
            text_a="Los bancos que incumplan esta disposición serán sancionados",
            text_b="Los bancos, que incumplan esta disposición, serán sancionados",
        ),
        Case(
            case_id="insercion",
            categoria="insercion",
            kind="insert",
            lexico_critico=[],
            direccion_esperada="restrictivo",
            nota="Añade una obligación de reporte nueva como artículo independiente.",
            build_b=lambda b: (
                b[: _index_containing(b, "Art. 35.") + 1]
                + [
                    Block(
                        "body",
                        "Art. 35 bis. Reporte adicional. Las entidades deberán remitir un "
                        "informe semestral de cumplimiento al ente regulador, detallando las "
                        "acciones adoptadas durante el periodo de adecuación.",
                    )
                ]
                + b[_index_containing(b, "Art. 35.") + 1 :]
            ),
            text_a=None,
            text_b=(
                "Art. 35 bis. Reporte adicional. Las entidades deberán remitir un informe "
                "semestral de cumplimiento al ente regulador, detallando las acciones "
                "adoptadas durante el periodo de adecuación."
            ),
        ),
        Case(
            case_id="eliminacion",
            categoria="eliminacion",
            kind="delete",
            lexico_critico=[],
            direccion_esperada="restrictivo",
            nota="Elimina la salvedad sobre obligaciones de reporte ya vigentes.",
            build_b=lambda b: _replace_once(
                b, ", sin perjuicio de las obligaciones de reporte que ya se encuentren vigentes.", "."
            ),
            text_a=(
                "sin perjuicio de las obligaciones de reporte que ya se encuentren vigentes."
            ),
            text_b=None,
        ),
        Case(
            case_id="movimiento",
            categoria="movimiento",
            kind="move",
            lexico_critico=[],
            direccion_esperada="equivalente",
            nota="Art. 37 y Art. 38 intercambian de posición; el texto de ambos no cambia.",
            build_b=lambda b: (
                b[: _index_containing(b, "Art. 37.")]
                + [b[_index_containing(b, "Art. 38.")], b[_index_containing(b, "Art. 37.")]]
                + b[_index_containing(b, "Art. 38.") + 1 :]
            ),
            text_a=ART_37,
            text_b=ART_37,
        ),
        Case(
            case_id="reflow",
            categoria="reflow_sin_cambio_de_fondo",
            kind="insert",
            lexico_critico=[],
            direccion_esperada=None,
            nota=(
                "Inserta un párrafo introductorio que reflowea todo el documento sin "
                "alterar el contenido normativo. El motor de diff no debe producir más de "
                "5 ChangeUnit para este par (criterio de aceptación WP-2)."
            ),
            build_b=lambda b: (
                b[:1]
                + [
                    Block(
                        "body",
                        "Este documento constituye una versión de prueba generada "
                        "automáticamente para validar el motor de comparación. No "
                        "representa normativa vigente ni tiene efectos jurídicos.",
                    )
                ]
                + b[1:]
            ),
            text_a=None,
            text_b=(
                "Este documento constituye una versión de prueba generada automáticamente "
                "para validar el motor de comparación. No representa normativa vigente ni "
                "tiene efectos jurídicos."
            ),
        ),
    ]


def generate_all(output_dir: Path = OUTPUT_DIR) -> list[GroundTruthEntry]:
    base = _base_blocks()
    ground_truth: list[GroundTruthEntry] = []
    for case in _cases():
        blocks_b = case.build_b(copy.deepcopy(base))
        _build_pdf(output_dir / f"{case.case_id}_a.pdf", base)
        _build_pdf(output_dir / f"{case.case_id}_b.pdf", blocks_b)
        ground_truth.append(
            GroundTruthEntry(
                case_id=case.case_id,
                categoria=case.categoria,
                kind=case.kind,
                lexico_critico=case.lexico_critico,
                direccion_esperada=case.direccion_esperada,
                text_a=case.text_a,
                text_b=case.text_b,
                nota=case.nota,
            )
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    gt_path = output_dir / "ground_truth.json"
    gt_path.write_text(
        json.dumps([asdict(e) for e in ground_truth], indent=2, ensure_ascii=False) + "\n"
    )
    return ground_truth


def main() -> None:
    entries = generate_all()
    print(f"generados {len(entries)} pares de fixtures en {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
