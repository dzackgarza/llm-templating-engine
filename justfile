default:
    @just --list

setup:
    uv sync --extra dev

test:
    uv run pytest

typecheck:
    uv run mypy src/llm_templating_engine

lint:
    uv run ruff check src/llm_templating_engine tests

format:
    uv run ruff format src/llm_templating_engine tests

check: typecheck lint test

build:
    uv build --no-sources

bump:
    uv version --bump minor
    uv lock

clean:
    python -c "from pathlib import Path; import shutil; [shutil.rmtree(path, ignore_errors=True) for path in [Path('dist'), Path('build'), Path('.pytest_cache'), Path('.mypy_cache'), Path('.ruff_cache')]]; [shutil.rmtree(path, ignore_errors=True) for path in Path('.').glob('*.egg-info')]"
