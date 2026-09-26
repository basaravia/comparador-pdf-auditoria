"""WP-0 criterio de aceptación: 'los fixtures existen' — y contienen lo planteado."""

import re
from pathlib import Path

import pymupdf
from fixtures.generator.generate_fixtures import generate_all


def _normalized_text(pdf_path: Path) -> str:
    raw = "".join(page.get_text() for page in pymupdf.open(pdf_path))
    return re.sub(r"\s+", " ", raw).strip()


def test_generate_all_produces_a_b_pairs_and_ground_truth(tmp_path):
    entries = generate_all(output_dir=tmp_path)

    assert len(entries) >= 10
    case_ids = {e.case_id for e in entries}
    assert case_ids == {
        "temporal",
        "deontico",
        "conjuncion",
        "parafrasis",
        "reescritura",
        "puntuacion",
        "insercion",
        "eliminacion",
        "movimiento",
        "reflow",
    }
    for entry in entries:
        assert (tmp_path / f"{entry.case_id}_a.pdf").exists()
        assert (tmp_path / f"{entry.case_id}_b.pdf").exists()
    assert (tmp_path / "ground_truth.json").exists()


def test_each_planted_change_is_present_in_the_expected_side(tmp_path):
    entries = generate_all(output_dir=tmp_path)

    for entry in entries:
        text_a = _normalized_text(tmp_path / f"{entry.case_id}_a.pdf")
        text_b = _normalized_text(tmp_path / f"{entry.case_id}_b.pdf")

        if entry.text_a is not None:
            assert re.sub(r"\s+", " ", entry.text_a).strip() in text_a, entry.case_id
        if entry.text_b is not None:
            assert re.sub(r"\s+", " ", entry.text_b).strip() in text_b, entry.case_id


def test_reflow_case_does_not_touch_normative_articles(tmp_path):
    """El caso 'reflow' es el fixture del criterio de aceptación WP-2 (≤5 ChangeUnit)."""
    generate_all(output_dir=tmp_path)

    text_a = _normalized_text(tmp_path / "reflow_a.pdf")
    text_b = _normalized_text(tmp_path / "reflow_b.pdf")

    for article_snippet in ("Art. 30.", "Art. 34.", "Art. 38."):
        assert article_snippet in text_a
        assert article_snippet in text_b
