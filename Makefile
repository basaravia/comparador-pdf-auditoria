.PHONY: sync test lint fixtures generate-types dev-backend dev-frontend

sync:
	cd backend && uv sync --group dev
	cd frontend && npm install

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint

fixtures:
	uv run --project backend python fixtures/generator/generate_fixtures.py

generate-types:
	cd backend && uv run python -m comparador.schemas.export
	cd frontend && node scripts/generate-types.mjs

dev-backend:
	cd backend && uv run uvicorn comparador.main:app --reload

dev-frontend:
	cd frontend && npm run dev
