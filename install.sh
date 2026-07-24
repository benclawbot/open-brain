#!/usr/bin/env sh
set -eu

REPO_URL="${OPENBRAIN_REPO_URL:-https://github.com/benclawbot/open-brain.git}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
HERMES_MODE="${OPENBRAIN_INSTALL_HERMES:-auto}"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
  echo "Python 3.11+ is required." >&2
  exit 1
}

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required.")
PY

if ! command -v pipx >/dev/null 2>&1; then
  "$PYTHON_BIN" -m pip install --user --upgrade pipx
  "$PYTHON_BIN" -m pipx ensurepath >/dev/null 2>&1 || true
  PIPX_BIN="$HOME/.local/bin/pipx"
else
  PIPX_BIN="$(command -v pipx)"
fi

if "$PIPX_BIN" list --short 2>/dev/null | grep -q 'openbrain'; then
  "$PIPX_BIN" upgrade openbrain
else
  "$PIPX_BIN" install "git+$REPO_URL"
fi

OPENBRAIN_BIN="$(command -v openbrain || true)"
if [ -z "$OPENBRAIN_BIN" ]; then
  OPENBRAIN_BIN="${PIPX_BIN_DIR:-$HOME/.local/bin}/openbrain"
fi

"$OPENBRAIN_BIN" configure

if [ "$HERMES_MODE" = "1" ] || [ "$HERMES_MODE" = "true" ] || { [ "$HERMES_MODE" = "auto" ] && command -v hermes >/dev/null 2>&1; }; then
  "$OPENBRAIN_BIN" install-hermes --force
fi

"$OPENBRAIN_BIN" doctor
cat <<'EOF'
Open Brain installed.

Useful commands:
  openbrain version-check
  openbrain update
  openbrain maintenance

Restart your shell if the openbrain command is not yet on PATH.
EOF
