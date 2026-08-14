# Comparador de PDFs para Papeles de Trabajo de Auditoría

Herramienta de comparación de PDFs normativos con localización de cambios (diff léxico +
geométrico + visual) y análisis semántico asistido por modelo, orientada a papeles de trabajo
de auditoría.

- **Fase 1**: ejecución local con Docker Model Runner (DMR).
- **Fase 2**: Azure AI Foundry.

Ver [`docs/arquitectura.md`](docs/arquitectura.md) para el documento de diseño completo y
[`CLAUDE.md`](CLAUDE.md) para los invariantes del proyecto.

## Cómo empezar (Fase 1)

Requisitos: Python 3.12 (gestionado por [`uv`](https://docs.astral.sh/uv/)), Node 22+.

```bash
make sync            # instala dependencias de backend y frontend
make test             # pytest, solo con FakeProvider — sin GPU ni red
make fixtures          # regenera fixtures/generated/*.pdf + ground_truth.json
make generate-types    # regenera frontend/src/types/change_unit.ts desde el schema
make dev-backend       # uvicorn --reload en :8000
make dev-frontend      # vite dev server en :5173
```

Para correr todo en Docker: `docker compose up --build` (ver la nota sobre DMR en
`docker-compose.yml`).
