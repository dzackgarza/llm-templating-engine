default:
    @just --list

install:
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

# Bump patch version, commit, and tag
bump-patch: check
    uv version --bump patch
    git add pyproject.toml uv.lock
    git commit -m "chore: bump version to v$(uv version | awk '{print $2}')"
    git tag "v$(uv version | awk '{print $2}')"

# Bump minor version, commit, and tag
bump-minor: check
    uv version --bump minor
    git add pyproject.toml uv.lock
    git commit -m "chore: bump version to v$(uv version | awk '{print $2}')"
    git tag "v$(uv version | awk '{print $2}')"

# Push commits and tags to trigger CI release
release: check
    git push && git push --tags
