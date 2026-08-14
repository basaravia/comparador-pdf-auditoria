# Comparador de PDFs para Papeles de Trabajo de Auditoría

Herramienta de comparación de PDFs normativos con localización de cambios (diff léxico +
geométrico + visual) y análisis semántico asistido por modelo, orientada a papeles de trabajo
de auditoría.

- **Fase 1**: ejecución local con Docker Model Runner (DMR).
- **Fase 2**: Azure AI Foundry.

Ver [`docs/arquitectura.md`](docs/arquitectura.md) para el documento de diseño completo y
[`CLAUDE.md`](CLAUDE.md) para los invariantes del proyecto.

## Cómo empezar (Fase 1)

Requisitos: Python 3.12 (gestionado por [`uv`](https://docs.astral.sh/uv/)), Node 20+.
`scripts/setup.sh check` verifica todo esto y da instrucciones de instalación si falta algo.

Camino más rápido — comprueba prerrequisitos, instala dependencias y levanta backend +
frontend en segundo plano:

```bash
scripts/setup.sh up      # equivalente a `scripts/setup.sh` (up es el default)
scripts/setup.sh down    # detiene lo que levantó
scripts/setup.sh status  # atajo a scripts/healthcheck.sh
```

Variables opcionales: `BACKEND_PORT` (default 8000), `FRONTEND_PORT` (default 5173).
Si no hay credenciales que configurar en esta fase (DMR corre local sin autenticación),
`scripts/setup.sh` crea `backend/.env` y `frontend/.env` desde sus `.env.example` la primera vez.

### `scripts/healthcheck.sh` — servicios y su indicador de correcto funcionamiento

| Servicio | URL | Indicador de correcto funcionamiento | Obligatorio |
|---|---|---|---|
| Backend (FastAPI) | `http://localhost:8000/health` | `200` con `{"status":"ok"}` | sí |
| Frontend (Vite dev server) | `http://localhost:5173/` | `200` (HTML de la SPA) | sí |
| Docker Model Runner (DMR) | `http://localhost:12434/engines/llama.cpp/v1/models` | `200` con la lista de modelos | no — recién hace falta desde WP-6b |

```bash
scripts/healthcheck.sh   # imprime la tabla de arriba y corre el chequeo; exit 0/1
```

### Comandos por partes (`make`)

```bash
make sync            # instala dependencias de backend y frontend
make test             # pytest, solo con FakeProvider — sin GPU ni red
make fixtures          # regenera fixtures/generated/*.pdf + ground_truth.json
make generate-types    # regenera frontend/src/types/change_unit.ts desde el schema
make dev-backend       # uvicorn --reload en :8000 (primer plano)
make dev-frontend      # vite dev server en :5173 (primer plano)
```

Para correr todo en Docker: `docker compose up --build` (ver la nota sobre DMR en
`docker-compose.yml`).
