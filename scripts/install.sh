#!/usr/bin/env bash
# Quorum installer. Idempotent; safe to re-run.
#
# Usage:
#     git clone https://github.com/<owner>/quorum.git ~/.quorum
#     ~/.quorum/scripts/install.sh
#
# What this does:
#   1. Verifies the prerequisites (uv, pnpm/npm).
#   2. Runs `uv sync` inside conductor/ to install Python deps.
#   3. Runs `pnpm install` (or npm install) inside ui/ to install JS deps.
#   4. Prints PATH export hints for the `quorum` console script.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDUCTOR_DIR="$REPO_ROOT/conductor"
UI_DIR="$REPO_ROOT/ui"

step() { printf '\033[1;36m›\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }

# ----- prerequisites -----
step "Checking prerequisites"

command -v uv >/dev/null 2>&1 || fail "uv not found. Install via 'curl -LsSf https://astral.sh/uv/install.sh | sh' or 'brew install uv'."
ok "uv: $(uv --version)"

JS_INSTALL=""
if command -v pnpm >/dev/null 2>&1; then
    JS_INSTALL="pnpm install"
    ok "pnpm: $(pnpm --version)"
elif command -v bun >/dev/null 2>&1; then
    JS_INSTALL="bun install"
    ok "bun: $(bun --version)"
elif command -v npm >/dev/null 2>&1; then
    JS_INSTALL="npm install"
    ok "npm: $(npm --version)"
else
    fail "No JS package manager found. Install pnpm (preferred), bun, or npm."
fi

# ----- conductor -----
step "Installing conductor (Python)"
cd "$CONDUCTOR_DIR"
uv sync
ok "Python deps installed at $CONDUCTOR_DIR/.venv"

# ----- UI -----
step "Installing UI ($JS_INSTALL)"
cd "$UI_DIR"
$JS_INSTALL
ok "JS deps installed at $UI_DIR/node_modules"

# ----- next steps -----
echo
ok "Quorum installed at $REPO_ROOT"
echo
echo "To run the conductor's CLI from any directory, expose it on your PATH:"
echo
echo "    export PATH=\"$CONDUCTOR_DIR/.venv/bin:\$PATH\""
echo
echo "Or invoke through uv from inside $CONDUCTOR_DIR:"
echo
echo "    uv run quorum --help"
echo
echo "Quickstart: see $REPO_ROOT/docs/quickstart.md"
