.PHONY: dev test lint migrate seed up down

dev:
	cd backend && uv run uvicorn app.main:app --reload --port 8000 & \
	cd frontend && npm run dev

test:
	cd backend && uv run pytest --cov=app --cov-report=term-missing
	cd frontend && npm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app
	cd frontend && npm run lint && npm run format:check && npm run typecheck

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m scripts.seed_demo

up:
	docker compose up --build

down:
	docker compose down
