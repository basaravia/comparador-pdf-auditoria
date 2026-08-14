"""Exporta el JSON Schema de ChangeUnit a schemas/change_unit.schema.json.

Fuente de verdad: el modelo Pydantic (change_unit.py). Este script solo serializa.
Uso: uv run --project backend python -m comparador.schemas.export
"""

import json
from pathlib import Path

from comparador.schemas.change_unit import ChangeUnit

REPO_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_PATH = REPO_ROOT / "schemas" / "change_unit.schema.json"


def main() -> None:
    schema = ChangeUnit.model_json_schema()
    schema["title"] = "ChangeUnit"
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
