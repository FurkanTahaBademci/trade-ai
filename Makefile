.PHONY: init dev down logs migrate smoke fmt config backup restore preflight production-smoke release leak-check

init:
	./ops/init-env.sh

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

config:
	docker compose config --quiet

backup:
	./ops/backup-postgres.sh

restore:
	./ops/restore-postgres.sh "$(FILE)"

preflight:
	./ops/preflight-production.sh

production-smoke:
	./ops/smoke-production.sh

release:
	./ops/release.sh "$(VERSION)"

leak-check:
	./ops/leak-check.sh
