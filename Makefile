.PHONY: setup up down test lint verify
setup:
	python scripts/setup_env.py
up:
	docker compose up --build -d --wait
down:
	docker compose down
test:
	python -m pytest -q
lint:
	python -m ruff check backend demo-services scripts
	npm run lint --prefix frontend
verify:
	python scripts/verify_stage1.py
	python scripts/verify_lifecycle.py
