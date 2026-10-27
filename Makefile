# Shortcuts for this project's commands. Run `make` (or `make help`) to list them.
# Locally, activate the venv first: source .venv/bin/activate
# CI (.github/workflows/ci.yml) calls these same targets, so local and CI checks
# can't drift apart.
#
# Recipe lines MUST be indented with a TAB, not spaces.

.PHONY: help lint test build check up down logs

help:
	@echo "make lint    - ruff: read the code for likely mistakes"
	@echo "make test    - pytest: run the validator tests"
	@echo "make build   - build the Docker images"
	@echo "make check   - lint + test + build: the local CI pipeline"
	@echo "make up      - start broker, sensor and bridge in the background"
	@echo "make down    - stop and remove the containers"
	@echo "make logs    - follow the bridge's logs (Ctrl+C to stop)"

lint:
	ruff check .

test:
	pytest -v

build:
	docker compose build

check: lint test build
	@echo "All checks passed - safe to push."

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f bridge
