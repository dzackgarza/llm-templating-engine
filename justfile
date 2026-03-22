set fallback := true
repo_root := justfile_directory()
python_qc_justfile := env_var_or_default("OPENCODE_PYTHON_QC_JUSTFILE", "/home/dzack/ai/quality-control/justfile")

default:
    @just test

install:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{repo_root}}"
    exec uv sync --extra dev

[private]
_format:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{repo_root}}"
    exec uv run ruff format src/llm_templating_engine tests

[private]
_lint:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{repo_root}}"
    exec uv run ruff check src/llm_templating_engine tests

[private]
_typecheck:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{repo_root}}"
    exec uv run mypy src/llm_templating_engine

[private]
_quality-control:
    #!/usr/bin/env bash
    set -euo pipefail
    exec just --justfile "{{python_qc_justfile}}" --working-directory "{{repo_root}}" test

test: _lint _typecheck _quality-control

check: test

build:
    uv build --no-sources

bump:
    uv version --bump minor
    uv lock

clean:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{repo_root}}"
    exec python -c "from pathlib import Path; import shutil; [shutil.rmtree(path, ignore_errors=True) for path in [Path('dist'), Path('build'), Path('.pytest_cache'), Path('.mypy_cache'), Path('.ruff_cache')]]; [shutil.rmtree(path, ignore_errors=True) for path in Path('.').glob('*.egg-info')]"

bump-patch: test
    uv version --bump patch
    git add pyproject.toml uv.lock
    git commit -m "chore: bump version to v$(uv version | awk '{print $2}')"
    git tag "v$(uv version | awk '{print $2}')"

bump-minor: test
    uv version --bump minor
    git add pyproject.toml uv.lock
    git commit -m "chore: bump version to v$(uv version | awk '{print $2}')"
    git tag "v$(uv version | awk '{print $2}')"

release: test
    git push && git push --tags
