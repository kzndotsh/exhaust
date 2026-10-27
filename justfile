# The gates CI runs, under the same names, so a local run matches CI.
# `just` lists the recipes. `just check` runs every gate.

set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Install the package with the dev dependency group.
sync:
    uv sync --group dev

# Ruff check and the format check, as CI runs them.
lint:
    uv run ruff check .
    uv run ruff format --check .

# Rewrite the code in the project's format.
fmt:
    uv run ruff format .

# Numpy-style docstrings that match their signatures. Ruff's D rules already run in `lint`.
docstrings:
    uv run pydoclint --config=pyproject.toml src

# Strict type check.
types:
    uv run basedpyright

# Tests. Extra arguments go to pytest, e.g. `just test -k scope_contract`.
test *args:
    uv run pytest {{ args }}

# The import contracts in pyproject.toml: which domain module may import which.
layers:
    uv run lint-imports

# The vertical catalog is in sync with skills/ (ADR 0016).
catalog:
    uv run exhaust catalog check

# Every gate CI runs, in CI's order.
check: lint docstrings types test layers catalog
