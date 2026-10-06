#!/bin/bash
# vendor.sh — copy the sdd plugin into a consuming project and pin it to git.
#
# Usage:
#   scripts/vendor.sh [--name NAME] [--dry-run] <target-project-dir>
#
# The script uses the consuming project's directory name as the local marketplace
# vendor key by default. Use --name to override. Use --dry-run to preview actions.

set -euo pipefail

# Ensure python3 is available (used to edit JSON safely)
if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is required but not found in PATH. Install python3 and retry." >&2
  exit 1
fi

HARNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DRY_RUN=false
CUSTOM_NAME=""

usage() {
  cat <<'USAGE' >&2
Usage: scripts/vendor.sh [--name NAME] [--dry-run] <target-project-dir>
  --name, -n     Specify vendor name (defaults to target directory name)
  --dry-run, -d  Show actions without copying or writing files
USAGE
  exit 1
}

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name|-n)
      shift
      CUSTOM_NAME="${1:-}"
      [ -n "$CUSTOM_NAME" ] || { echo "Error: --name requires an argument" >&2; usage; }
      shift
      ;;
    --dry-run|-d)
      DRY_RUN=true
      shift
      ;;
    --help|-h)
      cat <<'HELP'
Usage: scripts/vendor.sh [--name NAME] [--dry-run] <target-project-dir>
  --name, -n     Specify vendor name (defaults to target directory name)
  --dry-run, -d  Show actions without copying or writing files
HELP
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      ;;
    *)
      TARGET="$1"
      shift
      break
      ;;
  esac
done

[ -n "${TARGET:-}" ] || usage
[ -d "$TARGET" ] || { echo "Error: '$TARGET' is not a directory." >&2; exit 1; }

# Use the consuming repo directory name as the vendor key unless overridden
REPO_NAME="${CUSTOM_NAME:-$(basename "$(realpath "$TARGET")")}"
VENDOR_DIR="$TARGET/.claude/vendors/$REPO_NAME"
SETTINGS="$TARGET/.claude/settings.json"

echo "Vendoring sdd plugin into $TARGET as marketplace key '$REPO_NAME'..."
[ "$DRY_RUN" = true ] && echo "DRY-RUN: no changes will be made"

# ------------------------------------------------------------------
# 1. Copy plugin files (idempotent — overwrites any previous vendor copy)
# ------------------------------------------------------------------
if [ "$DRY_RUN" = true ]; then
  echo "  DRY-RUN: would create $VENDOR_DIR and copy plugin files into it"
else
  mkdir -p "$VENDOR_DIR"
  rm -rf "${VENDOR_DIR:?}/.claude-plugin" "${VENDOR_DIR:?}/plugins"
  cp -r "$HARNESS_DIR/.claude-plugin" "$VENDOR_DIR/"
  cp -r "$HARNESS_DIR/plugins"        "$VENDOR_DIR/"
  echo "  Copied plugin files → .claude/vendors/$REPO_NAME/"
fi

# ------------------------------------------------------------------
# 2. Copy skill files to .claude/skills/ so Claude Code discovers them
# ------------------------------------------------------------------
SKILLS_SRC="$HARNESS_DIR/plugins/sdd/skills"
SKILLS_DST="$TARGET/.claude/skills"

if [ "$DRY_RUN" = true ]; then
  echo "  DRY-RUN: would copy skills to $SKILLS_DST/sdd:<name>/"
else
  for skill_dir in "$SKILLS_SRC"/*/; do
    skill_name="sdd:$(basename "$skill_dir")"
    mkdir -p "$SKILLS_DST/$skill_name"
    cp "$skill_dir/SKILL.md" "$SKILLS_DST/$skill_name/SKILL.md"
  done
  echo "  Copied skills → .claude/skills/sdd:<name>/"
fi

# ------------------------------------------------------------------
# 3. Upsert settings.json (create or update)
# ------------------------------------------------------------------
if [ "$DRY_RUN" = true ]; then
  if [ -f "$SETTINGS" ]; then
    echo "  DRY-RUN: would update $SETTINGS to add marketplace entry '$REPO_NAME' -> .claude/vendors/$REPO_NAME and enable sdd@$REPO_NAME"
  else
    echo "  DRY-RUN: would create $SETTINGS with marketplace '$REPO_NAME' -> .claude/vendors/$REPO_NAME and enable sdd@$REPO_NAME"
  fi
else
  mkdir -p "$(dirname "$SETTINGS")"
  if [ -f "$SETTINGS" ]; then
    # Update in-place: set the marketplace source to the local path and enable the plugin
    python3 - "$SETTINGS" "$REPO_NAME" <<'PYEOF'
import json, sys
path = sys.argv[1]
vendor = sys.argv[2]
with open(path) as fh:
    settings = json.load(fh)

settings.setdefault('extraKnownMarketplaces', {})[vendor] = {
    'source': {'source': 'directory', 'path': f'.claude/vendors/{vendor}'}
}
settings.setdefault('enabledPlugins', {})[f'sdd@{vendor}'] = True

with open(path, 'w') as fh:
    json.dump(settings, fh, indent=2)
    fh.write('\n')

print(f"  Updated {path}")
PYEOF
  else
    cat > "$SETTINGS" <<JSON
{
  "extraKnownMarketplaces": {
    "$REPO_NAME": {
      "source": { "source": "directory", "path": ".claude/vendors/$REPO_NAME" }
    }
  },
  "enabledPlugins": {
    "sdd@$REPO_NAME": true
  }
}
JSON
    echo "  Created $SETTINGS"
  fi
fi

# ------------------------------------------------------------------
# 3. Done — print next steps
# ------------------------------------------------------------------
HARNESS_VERSION="$(python3 -c "import json; print(json.load(open('$HARNESS_DIR/plugins/sdd/.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo "unknown")"

echo ""
if [ "$DRY_RUN" = true ]; then
  echo "DRY-RUN: no files were changed."
  echo ""
  echo "Planned actions:"
  echo "  - copy plugin files to .claude/vendors/$REPO_NAME/"
  echo "  - copy skills to .claude/skills/sdd:<name>/"
  echo "  - update $SETTINGS to enable sdd@$REPO_NAME"
  echo ""
  echo "To perform these actions, re-run without --dry-run."
else
  echo "✓ sdd plugin v${HARNESS_VERSION} vendored to .claude/vendors/$REPO_NAME/"
  echo "✓ skills copied to .claude/skills/sdd:<name>/"
  echo "✓ settings.json updated to use the local copy (marketplace key: $REPO_NAME)"
  echo ""
  echo "Next steps:"
  echo "  cd \"$(realpath "$TARGET")\""
  echo "  git add .claude/"
  echo "  git commit -m 'chore: vendor sdd plugin for $REPO_NAME'"
  echo ""
  echo "Then open Claude Code and run /sdd:sdd-init (if you haven't already)."
  echo "To update the vendor copy in future, re-run this script from an updated harness checkout."
fi
