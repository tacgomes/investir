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

info "[1/6] Running Flake8"
if command -v flake8 > /dev/null; then
    run_tool flake8 .
else
    warn "'flake8' command not found, skipping check"
fi

info "[2/6] Running Black"
if command -v black > /dev/null; then
    run_tool black --check .
else
    warn "'black' command not found, skipping check"
fi

info "[3/6] Running isort"
if command -v isort > /dev/null; then
    run_tool isort . --check-only --diff
else
    warn "'isort' command not found, skipping check"
fi

info "[4/6] Running Pylint"
if command -v pylint > /dev/null; then
    run_tool pylint --score no $(git ls-files '*.py')
else
    warn "'pylint' command not found, skipping check"
fi

info "[5/6] Running Mypy"
if command -v mypy > /dev/null; then
    run_tool mypy --non-interactive --install-types --no-color-output .
else
    warn "'mypy' command not found, skipping check"
fi

info "[6/6] Running Pytest"
if command -v pytest > /dev/null; then
    run_tool pytest --no-header
else
    warn "'pytest' command not found, skipping check"
fi
