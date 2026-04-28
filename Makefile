.PHONY: help bootstrap install test test-e2e lint format check run cli seed fonts clean release

help:
	@echo "Hemiciclo -- comandos disponiveis:"
	@echo "  bootstrap      - Setup completo (venv + deps + hooks)"
	@echo "  install        - Sincroniza dependencias"
	@echo "  test           - Roda testes (unit + integracao)"
	@echo "  test-e2e       - Roda testes end-to-end (lento)"
	@echo "  lint           - Ruff check + Mypy strict"
	@echo "  format         - Ruff format"
	@echo "  check          - lint + test (CI local)"
	@echo "  run            - Sobe Streamlit em localhost:8501"
	@echo "  cli            - Atalho pra hemiciclo CLI (use ARGS=...)"
	@echo "  seed           - Popula ~/hemiciclo com dados seed pra dev"
	@echo "  fonts          - Verifica integridade SHA256 dos TTFs Inter+JetBrainsMono"
	@echo "  clean          - Remove __pycache__, .pytest_cache, .ruff_cache"
	@echo "  release VERSION=x.y.z - Cria tag e dispara release"

bootstrap:
	@if [ ! -d .venv ]; then uv venv; else echo ".venv ja existe; reutilizando."; fi
	uv sync --all-extras
	@uv run pre-commit install || echo "[aviso] pre-commit install nao foi aplicado (provavel core.hooksPath global). Rode 'git config --unset-all core.hooksPath' e tente de novo se quiser hooks locais ativos."
	@echo "Bootstrap concluido. Ative com: source .venv/bin/activate"

install:
	uv sync --all-extras

test:
	uv run pytest tests/unit tests/integracao -v --cov=src/hemiciclo --cov-report=term-missing

test-e2e:
	uv run pytest tests/e2e -v -m slow

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy --strict src

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

check: lint test

run:
	uv run streamlit run src/hemiciclo/dashboard/app.py

cli:
	uv run hemiciclo $(ARGS)

seed:
	uv run python scripts/seed_dados.py

fonts:
	uv run python scripts/baixar_fontes.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov

release:
	@test -n "$(VERSION)" || (echo "Use: make release VERSION=x.y.z" && exit 1)
	git tag -a v$(VERSION) -m "Release v$(VERSION)"
	git push origin v$(VERSION)
