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
    if command -v "$1" > /dev/null; then
        (cd "${PROJECT_DIR}"; $@) || error "Check failed"
    else
        warn "$1: command not found, skipping check"
    fi
}

info "[1/4] Running linter"
run_tool ruff check

info "[2/4] Running style checker"
run_tool ruff format --check

info "[3/4] Running type checker"
run_tool mypy --non-interactive --install-types --no-color-output .

info "[4/4] Running unit tests"
run_tool pytest --no-header
