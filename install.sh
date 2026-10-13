#!/usr/bin/env bash
set -euo pipefail

# Install the VSDD CLI once for the current user.
# Usage: bash install.sh [prefix]
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${1:-${VSDD_PREFIX:-$HOME/.local}}"
PREFIX="$(mkdir -p "$PREFIX" && cd "$PREFIX" && pwd)"
SHARE_DIR="$PREFIX/share/vsdd"
BIN_DIR="$PREFIX/bin"

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required (3.10+)." >&2; exit 1; }
python3 - <<'PY' || { echo "ERROR: Python 3.10+ is required." >&2; exit 1; }
import sys
if sys.version_info < (3, 10):
    raise SystemExit(1)
PY

mkdir -p "$SHARE_DIR" "$BIN_DIR"
# Copy runtime assets. The installed command reads Skills/templates from SHARE_DIR.
for item in .agents .vsdd scripts docs examples README.md README.zh-CN.md LICENSE; do
  if [ -e "$SOURCE_DIR/$item" ]; then
    rm -rf "$SHARE_DIR/$item"
    cp -R "$SOURCE_DIR/$item" "$SHARE_DIR/$item"
  fi
done

printf '%s\n' \
  '#!/usr/bin/env bash' \
  'set -e' \
  "export VSDD_HOME=\"\${VSDD_HOME:-$SHARE_DIR}\"" \
  'exec python3 "$VSDD_HOME/scripts/vsdd.py" "$@"' \
  > "$BIN_DIR/vsdd"
chmod 755 "$BIN_DIR/vsdd"

PROFILE_LINE='export PATH="$HOME/.local/bin:$PATH"'
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    if [ "$PREFIX" = "$HOME/.local" ]; then
      for profile in "$HOME/.bashrc" "$HOME/.zshrc"; do
        if [ -f "$profile" ] && ! grep -Fq 'export PATH="$HOME/.local/bin:$PATH"' "$profile"; then
          printf '\n# VSDD user-local commands\n%s\n' "$PROFILE_LINE" >> "$profile"
        fi
      done
    fi
    echo "NOTE: Add $BIN_DIR to PATH if it is not already present."
    ;;
esac

echo "VSDD installed to $BIN_DIR/vsdd"
echo "Runtime assets: $SHARE_DIR"
echo "Try: $BIN_DIR/vsdd --version"
if ! command -v vsdd >/dev/null 2>&1; then
  echo 'Open a new shell or run: export PATH="$HOME/.local/bin:$PATH"'
fi
