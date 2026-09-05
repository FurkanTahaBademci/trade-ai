.PHONY: dev down logs migrate smoke fmt

dev:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api worker

migrate:
	docker compose exec api alembic upgrade head

smoke:
	docker compose exec api python -m scripts.smoke_sources

fmt:
	cd backend && ruff format . && ruff check --fix .
