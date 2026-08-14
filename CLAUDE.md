# Comparador de PDFs para Papeles de Trabajo de Auditoría

Ver [`docs/arquitectura.md`](docs/arquitectura.md) para el documento de diseño completo
(decisiones, contratos, capas del motor de diff, work packages). Este archivo contiene
únicamente los invariantes que deben sostenerse en cada sesión.

## Invariantes del proyecto

1. Coordenadas: puntos PDF, origen arriba-izquierda, página 1-indexada.
   Toda bbox lleva `page_size` para escalar en el frontend.
2. Ninguna llamada a modelo fuera de `ModelGateway`. Prohibido importar
   `openai` o `httpx` fuera de `backend/src/comparador/gateway/`.
3. Un fallo de modelo NUNCA produce contenido. `status="failed"`, visible y reintentable.
4. El diff se calcula solo en backend. El frontend dibuja, no calcula.
5. Todo cambio al esquema de `ChangeUnit` regenera los tipos TS en el mismo commit
   (`make generate-types` — ver `scripts/`).
6. Todo análisis registra `provenance` (provider, modelo, prompt_version, hash).
7. Los tests corren con `FakeProvider`. Ningún test requiere GPU ni red.
8. Un ancla es una referencia posicional, NO una afirmación de que el contenido
   es igual. Toda ancla se reverifica con `hash_estricto` (puntuación incluida).
9. Ningún umbral de similitud puede eliminar una fila del reporte. Los embeddings
   despriorizan; nunca descartan.
10. Un cambio que toca léxico crítico (deóntico, conjunción, negación, temporal,
    umbral) nunca se despriorización automáticamente.
11. El modelo cita spans literales. Si el span no existe en el contexto,
    el análisis es `failed`.
12. El sistema propone; el auditor decide. Nada se cierra automáticamente.

## Estructura del repo

```
backend/                  FastAPI + Pydantic + motor de diff (Python 3.12, uv)
  src/comparador/
    schemas/              ChangeUnit y modelos anidados (fuente de verdad)
    gateway/               ModelGateway: base.py, fake.py, dmr.py, config.py
  tests/                  pytest, solo FakeProvider
frontend/                 React + TS + Vite
  src/types/              Tipos generados desde schemas/change_unit.schema.json — NO editar a mano
schemas/                  change_unit.schema.json exportado (generado, no fuente)
fixtures/generator/       Generador de PDFs sintéticos (reportlab) + ground_truth.json
config/models.yaml        Configuración del ModelGateway por rol lógico (Fase 1: DMR)
prompts/                  Prompts versionados, nunca embebidos en código
scripts/setup.sh          Prerrequisitos + arranque de backend/frontend en local (check|up|down|status)
scripts/healthcheck.sh    Documenta los servicios y su indicador de correcto funcionamiento
docs/arquitectura.md      Documento de diseño congelado
```

`backend/.env.example` y `frontend/.env.example` documentan la configuración no-secreta
que `scripts/setup.sh` usa al levantar cada servicio (puertos, `VITE_API_BASE_URL`).
Fase 1 no tiene credenciales reales — DMR corre local sin autenticación. Cuando WP-11
(Azure Foundry) añada Entra ID, sus variables se documentan ahí, nunca como api_key.

## Convención de ramas / PRs

Un work package (WP-N del documento de diseño) = una rama `feat/wpN-<slug>` = un PR.
Cerrar cuando el criterio de aceptación del WP se cumple, no cuando "parece que funciona".
