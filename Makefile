dc = docker compose -f compose.yaml -f .devcontainer/docker-compose.yml

build: setup-configmaps
	$(dc) build

run: setup-configmaps
	$(dc) up -d app

shell:
	$(dc) exec -it app /bin/bash

# this command runs the daemon process that monitor and reconciles image updates
reconcile-image-updates: run
	$(dc) exec -e PYTHONPATH=/app -it app python3 kollie/app/cli/bin.py reconcile

rebuild-env-configs: run
	$(dc) exec -e PYTHONPATH=/app -it app python3 kollie/app/cli/bin.py rebuild-env-configs

lint:
	$(dc) run --rm app poetry run ruff check kollie tests .

fix:
	$(dc) run --rm app poetry run ruff check kollie tests --fix .

fix-unsafe:
	$(dc) run --rm app poetry run ruff check kollie tests --fix --unsafe-fixes .

test:
	$(dc) run -e APPLICATION_STAGE=test -e KOLLIE_COMMON_SUBSTITUTIONS_JSON_PATH=tests/test_common_substitutions.json -e KOLLIE_DEFAULT_FLUX_REPOSITORY=test-repo --rm app poetry run pytest -sxvvv

type-check:
	$(dc) run --rm app poetry run mypy .

setup-secrets:
	echo "X_AUTH_REQUEST_EMAIL=$$(git config user.email)" > current_user.env

precommit: lint type-check test

setup-configmaps:
	@if [ ! -f app_templates.json ]; then touch app_templates.json && echo "app_templates.json created"; fi
	@if [ ! -f app_bundles.json ]; then touch app_bundles.json && echo "app_bundles.json created"; fi

update-packages:
	$(dc) run --rm app poetry lock
