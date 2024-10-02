#!/usr/bin/env sh

set -eu

RED="\033[1;31m"
GREEN="\033[1;32m"
YELLOW="\033[1;33m"
NOCOLOR="\033[0m"

PROJECT_DIR="$(readlink -f "$(dirname "$0")/..")"

info() {
    printf "${GREEN}${1}${NOCOLOR}\n"
}

warn() {
    printf "${YELLOW}${1}${NOCOLOR}\n"
}

error() {
    printf "${RED}${1}${NOCOLOR}\n"
    exit 1
}

run_tool() {
    (cd "${PROJECT_DIR}"; $@) || error "Check failed"
}

info "[1/4] Running linter"
if command -v ruff > /dev/null; then
    run_tool ruff check
else
    warn "'ruff' command not found, skipping check"
fi

info "[2/4] Running style checker"
if command -v ruff > /dev/null; then
    run_tool ruff format --check
else
    warn "'ruff' command not found, skipping check"
fi

info "[3/4] Running type checker"
if command -v mypy > /dev/null; then
    run_tool mypy --non-interactive --install-types --no-color-output .
else
    warn "'mypy' command not found, skipping check"
fi

info "[4/4] Running unit tests"
if command -v pytest > /dev/null; then
    run_tool pytest --no-header
else
    warn "'pytest' command not found, skipping check"
fi
