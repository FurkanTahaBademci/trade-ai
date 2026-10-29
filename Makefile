.PHONY: init dev down logs migrate create-admin smoke fmt config backup restore preflight production-smoke release leak-check

init:
	./ops/init-env.sh

dev:
	SOURCE_COMMIT=$$(git rev-parse HEAD 2>/dev/null) docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api worker

migrate:
	docker compose exec api alembic upgrade head

# Kullanim: make create-admin EMAIL=yonetici@example.com (parola sorulur)
create-admin:
	docker compose exec api python -m scripts.create_admin --email "$(EMAIL)"

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
