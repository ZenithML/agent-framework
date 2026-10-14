#!/usr/bin/env bash
# Put the ci-runner command on PATH by linking bin/ci-runner into a bin directory.
#
# Usage:
#   plugins/ci-runner/install.sh [--bin-dir DIR] [--uninstall]
#
# DIR defaults to ~/.local/bin. The link points into this checkout, so
# `git pull` here updates the command. Bash 3.2 safe (macOS /bin/bash).
set -euo pipefail

BIN_DIR="$HOME/.local/bin"
UNINSTALL=false
while [ $# -gt 0 ]; do
  case "$1" in
    --bin-dir) [ $# -ge 2 ] || { echo "--bin-dir needs a path" >&2; exit 1; }; BIN_DIR="$2"; shift 2 ;;
    --uninstall) UNINSTALL=true; shift ;;
    --help|-h) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option '$1'" >&2; exit 1 ;;
  esac
done

SRC="$(cd "$(dirname "$0")" && pwd)/bin/ci-runner"
DEST="$BIN_DIR/ci-runner"

if $UNINSTALL; then
  if [ -L "$DEST" ]; then rm "$DEST"; echo "Removed $DEST."; else echo "No ci-runner link at $DEST."; fi
  exit 0
fi

if [ -e "$DEST" ] && [ ! -L "$DEST" ]; then
  echo "$DEST exists and is not a link; leaving it alone." >&2
  exit 1
fi
mkdir -p "$BIN_DIR"
ln -sf "$SRC" "$DEST"
echo "Linked $DEST -> $SRC"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Note: $BIN_DIR is not on your PATH. Add it, e.g.: export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac
"$DEST" version
