.PHONY: install dev test lint seed docker-up docker-down docker-logs smoke clean

PYTHON ?= python
PNPM ?= pnpm

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"
	cd apps/web && $(PNPM) install

dev:
	@echo "Run in three terminals:"
	@echo "  1) uvicorn app.main:app --reload --app-dir apps/api --port 8000"
	@echo "  2) python -m worker.main"
	@echo "  3) cd apps/web && pnpm dev"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .
	cd apps/web && $(PNPM) run lint || true

seed:
	$(PYTHON) -m chief_editor.services.seed

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f --tail=200

smoke:
	@curl -sf http://localhost:8000/health && echo " health OK" || echo " health FAIL"
	@curl -sf http://localhost:8000/status | head -c 200 && echo "" || echo " status FAIL"
	@curl -sf http://localhost:8000/trends | head -c 200 && echo "" || echo " trends FAIL"

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
	rm -rf apps/web/.next apps/web/node_modules
