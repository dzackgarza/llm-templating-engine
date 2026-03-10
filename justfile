# Justfile for template-parsing-engine

# Default recipe
default:
    @just --list

# Install dependencies and package
install:
    uv pip install -e ".[dev]"

# Run tests
test:
    uv run pytest

# Run tests with coverage
test-cov:
    uv run pytest --cov=template_parsing_engine --cov-report=term-missing

# Run type checking
typecheck:
    uv run mypy src/template_parsing_engine

# Run linting
lint:
    uv run ruff check src/template_parsing_engine tests

# Format code
format:
    uv run ruff format src/template_parsing_engine tests

# Run all checks
check: typecheck lint test

# Build package
build:
    uv build

# Clean build artifacts
clean:
    rm -rf dist/ build/ *.egg-info .pytest_cache .mypy_cache .ruff_cache

# Test CLI directly
cli-test:
    echo '{"template_path": "tests/fixtures/basic.md", "output_mode": "body", "variables": {"string_vars": {"name": "Test"}}}' | uv run template-parsing-engine

# Full release process (build + check)
release: check build
    @echo "Package ready for release"
