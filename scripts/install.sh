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

# ----- expose `quorum` globally -----
# `uv tool install -e` drops a `quorum` shim into uv's tool-bin
# directory (typically `~/.local/bin`). Re-running with `--force`
# upgrades the link in place, so the script stays idempotent.
step "Installing the 'quorum' command globally"
cd "$CONDUCTOR_DIR"
uv tool install --force -e .
TOOL_BIN="$(uv tool dir --bin 2>/dev/null || echo "$HOME/.local/bin")"
ok "Installed shim at $TOOL_BIN/quorum"

# Make sure `~/.local/bin` (or wherever uv tools live) is on PATH for
# future shells. `uv tool update-shell` is idempotent and edits the
# user's shell rc only if needed.
if ! command -v quorum >/dev/null 2>&1; then
    step "Adding $TOOL_BIN to PATH (via 'uv tool update-shell')"
    uv tool update-shell || warn "uv tool update-shell failed — add $TOOL_BIN to PATH manually."
fi

# ----- next steps -----
echo
ok "Quorum installed at $REPO_ROOT"
echo
if command -v quorum >/dev/null 2>&1; then
    echo "Try it now:"
    echo
    echo "    quorum --help"
else
    echo "Open a new terminal (or 'source ~/.zshrc') so PATH picks up $TOOL_BIN, then:"
    echo
    echo "    quorum --help"
fi
echo
echo "Quickstart: see $REPO_ROOT/docs/quickstart.md"
