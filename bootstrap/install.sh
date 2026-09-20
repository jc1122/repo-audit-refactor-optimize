#!/usr/bin/env bash
# Install repo-audit-refactor-optimize v1.0.0.
#
# Installs the same skill body for Codex and Claude Code, then installs the
# detection runtime (repo-audit-checks, which provides the `repo-audit` CLI)
# into an ISOLATED venv — never into the system Python (PEP 668 is honored:
# no system-exemption flags, no global pip installs).
#
#   ./bootstrap/install.sh --harness codex --core <spec>
#   ./bootstrap/install.sh --dest /path/to/skills --core /path/to/repo-audit-skills
#   ./bootstrap/install.sh --harness claude --core 'git+https://github.com/jc1122/repo-audit-skills@v1.0.0' --dry-run
#   ./bootstrap/install.sh --dest DIR --venv /existing/env --core <spec>
#
# --core accepts a local directory, wheel/sdist file, or any pip requirement
# string. Tests may stage local sibling checkouts here; the skill runtime
# itself never hardcodes a home-directory default for the core.
# --venv reuses an existing environment instead of creating the default
# <dest>/repo-audit-venv. --python selects the base interpreter used to
# create the default venv (default: python3).
#
# Failure model: the new body and venv are staged, installed, and probed
# BEFORE anything existing is touched. Any failure exits nonzero and leaves
# the previous install (if any) intact; no partial venv or half-copied skill
# is left behind, and success is never reported unless the final on-disk
# verification passes.
#
# Execution model: every step runs through `run`, which exec's its arguments
# directly — never through a shell re-parse — so hostile-looking values
# (spaces, quotes, `$(...)`) in --dest/--core/--venv stay literal text. Under
# --dry-run the same argv is printed shell-quoted (`%q`) instead of executed.
set -euo pipefail

SKILL_NAME="repo-audit-refactor-optimize"
SKILL_VERSION="1.0.0"
DEFAULT_CORE="git+https://github.com/jc1122/repo-audit-skills@v1.0.0"
VENV_DIRNAME="repo-audit-venv"
SHIPPED_SCRIPTS="repo-audit run_diagnosis_wave.py"
SHIPPED_REFS="acceptance.md prioritization.md remediation-playbook.md verification.md MIGRATION.md"

HARNESS=""
DEST=""
CORE="$DEFAULT_CORE"
VENV=""
VENV_GIVEN=0
PYTHON_BIN="python3"
DRY_RUN=0
SKIP_CORE=0

fail() { echo "install failed: $1" >&2; exit 1; }

usage() {
  sed -n '2,28p' "$0"
  echo "options: --harness codex|claude  --dest DIR  --core SPEC  --venv DIR  --python BIN  --skip-core  --dry-run"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --harness) HARNESS="$2"; shift 2;;
    --dest) DEST="$2"; shift 2;;
    --core) CORE="$2"; shift 2;;
    --venv) VENV="$2"; VENV_GIVEN=1; shift 2;;
    --python) PYTHON_BIN="$2"; shift 2;;
    --skip-core) SKIP_CORE=1; shift;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "unknown arg: $1" >&2; usage >&2; exit 2;;
  esac
done

case "$HARNESS" in
  "") ;;
  codex|claude) ;;
  *) echo "unknown harness: $HARNESS (expected codex|claude)" >&2; exit 2;;
esac

if [ -z "$DEST" ]; then
  if [ -n "${AGENT_SKILLS_HOME:-}" ]; then DEST="$AGENT_SKILLS_HOME/skills"
  elif [ "$HARNESS" = "claude" ]; then DEST="$HOME/.claude/skills"
  else DEST="$HOME/.agents/skills"; fi
fi

# Canonicalize DEST so all derived paths are absolute and literal.
# Timestamped backups live OUTSIDE the scanned skills root: a backup carries a
# SKILL.md and must never be discoverable as a second skill entry.
DEST_PARENT="$(dirname "$DEST")"

# Default isolated environment lives next to the skill, never in the system.
if [ -z "$VENV" ]; then
  VENV="$DEST/$VENV_DIRNAME"
fi

# Argv-safe step runner: direct exec, no shell re-parse. Under --dry-run,
# print the exact argv shell-quoted instead of running it.
run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf 'DRY:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "== $SKILL_NAME v$SKILL_VERSION install =="
echo "dest: $DEST/$SKILL_NAME"
echo "harness: ${HARNESS:-default}"
echo "venv: ${VENV:-"(skipped)"}"
echo "core: ${CORE:-"(skipped)"}"

if [ "$DRY_RUN" -eq 1 ]; then
  # Dry-run never creates: allow a not-yet-existing parent (CI smoke).
  if [ -d "$DEST_PARENT" ]; then
    DEST="$(cd "$DEST_PARENT" && pwd)/$(basename "$DEST")"
    BACKUP_ROOT="$(cd "$DEST_PARENT" && pwd)/.repo-audit-install-backups"
  else
    BACKUP_ROOT="$DEST_PARENT/.repo-audit-install-backups"
  fi
else
  # Create the parent chain (harmless on failure: no install content yet).
  mkdir -p "$DEST_PARENT" || fail "cannot create parent of --dest: $DEST_PARENT"
  DEST="$(cd "$DEST_PARENT" && pwd)/$(basename "$DEST")"
  BACKUP_ROOT="$(cd "$DEST_PARENT" && pwd)/.repo-audit-install-backups"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  run mkdir -p "$DEST/$SKILL_NAME"
  run cp "$SRC_DIR/SKILL.md" "$DEST/$SKILL_NAME/SKILL.md"
  run mkdir -p "$DEST/$SKILL_NAME/references" "$DEST/$SKILL_NAME/scripts"
  # shellcheck disable=SC2086
  run cp "$SRC_DIR"/references/{acceptance.md,prioritization.md,remediation-playbook.md,verification.md,MIGRATION.md} "$DEST/$SKILL_NAME/references/"
  run cp "$SRC_DIR/scripts/repo-audit" "$SRC_DIR/scripts/run_diagnosis_wave.py" "$DEST/$SKILL_NAME/scripts/"
  if [ "$SKIP_CORE" -eq 0 ]; then
    run "$PYTHON_BIN" -m venv "$VENV"
    run "$VENV/bin/python" -m pip install "$CORE"
    run "$VENV/bin/python" "$VENV/bin/repo-audit" scan --list-checks
  fi
  echo "== done (dry run: nothing created) =="
  exit 0
fi

# From here on every mutation goes to a private work dir first; the live
# locations are only swapped in after full verification (failure model above).
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
STAGE="$WORK/skill"
VENV_NEW="$WORK/venv"

# 1. Stage the skill body (same content for both harnesses).
run mkdir -p "$STAGE/references" "$STAGE/scripts"
run cp "$SRC_DIR/SKILL.md" "$STAGE/SKILL.md"
run cp "$SRC_DIR/references/acceptance.md" "$SRC_DIR/references/prioritization.md" "$SRC_DIR/references/remediation-playbook.md" "$SRC_DIR/references/verification.md" "$SRC_DIR/references/MIGRATION.md" "$STAGE/references/"
run cp "$SRC_DIR/scripts/repo-audit" "$SRC_DIR/scripts/run_diagnosis_wave.py" "$STAGE/scripts/"

# 2. Provide the isolated runtime (default) or reuse the given environment.
if [ "$SKIP_CORE" -eq 0 ]; then
  if [ "$VENV_GIVEN" -eq 0 ]; then
    # Default: build a fresh venv in staging, swap in only once probed.
    "$PYTHON_BIN" -m venv "$VENV_NEW" \
      || fail "venv creation failed (Debian/Ubuntu stock Python needs the python3-venv package: apt install python3-venv)"
    "$VENV_NEW/bin/python" -m pip install "$CORE" \
      || fail "core install into isolated venv failed; previous install (if any) untouched"
    # Run the CLI through the venv python (never the shebang) so staging
    # paths with spaces still probe correctly; same for the final verify.
    "$VENV_NEW/bin/python" "$VENV_NEW/bin/repo-audit" scan --list-checks >/dev/null \
      || fail "fresh CLI probe failed; previous install (if any) untouched"
  else
    # Explicit environment: must already exist; install in place, probe, fail loud.
    [ -x "$VENV/bin/python" ] \
      || fail "--venv $VENV has no bin/python; refusing to create or repair it"
    "$VENV/bin/python" -m pip install "$CORE" \
      || fail "core install into --venv environment failed"
    "$VENV/bin/python" "$VENV/bin/repo-audit" scan --list-checks >/dev/null \
      || fail "CLI probe in --venv environment failed"
  fi
fi

# 3. Record the venv for the launcher only when it is NOT the default
# relative location (keeps installed bodies byte-identical across harnesses):
# explicit --venv, or --skip-core reusing a previously installed explicit env.
if [ "$VENV_GIVEN" -eq 1 ]; then
  if [ "$SKIP_CORE" -eq 0 ] || [ -x "$VENV/bin/repo-audit" ]; then
    printf '%s\n' "$VENV" > "$STAGE/scripts/.venv-path"
  fi
fi

# 4. Swap staged body into place (previous install preserved on any error).
# Superseded trees move to a TIMESTAMPED backup OUTSIDE the scanned skills
# root: a backup carries a SKILL.md and must never be discoverable as a
# second skill entry. Only the newest few backups are kept (recovery).
BACKUP_TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$BACKUP_TS"
prune_backups() {
  [ -d "$BACKUP_ROOT" ] || return 0
  kept=0
  for old in $(ls -1 "$BACKUP_ROOT" | sort -r); do
    case "$old" in
      ????????-??????) ;;
      *) continue ;;
    esac
    kept=$((kept + 1))
    if [ "$kept" -gt 3 ]; then
      rm -rf "$BACKUP_ROOT/$old"
    fi
  done
}
run mkdir -p "$DEST"
made_backup=0
if [ -d "$DEST/$SKILL_NAME" ]; then
  run mkdir -p "$BACKUP_DIR"
  run mv "$DEST/$SKILL_NAME" "$BACKUP_DIR/$SKILL_NAME"
  made_backup=1
fi
run mv "$STAGE" "$DEST/$SKILL_NAME"
if [ "$SKIP_CORE" -eq 0 ] && [ "$VENV_GIVEN" -eq 0 ]; then
  if [ -d "$VENV" ]; then
    run mkdir -p "$BACKUP_DIR"
    run mv "$VENV" "$BACKUP_DIR/$VENV_DIRNAME"
    made_backup=1
  fi
  run mv "$VENV_NEW" "$VENV"
  # A moved venv keeps absolute shebangs pointing at the staging dir, which
  # the EXIT trap then deletes. Rewrite them to the final path (exact bytes,
  # first line only) before anything executes from the new location.
  "$PYTHON_BIN" - "$VENV_NEW" "$VENV" <<'PY'
import os, sys
old_prefix, new_prefix = sys.argv[1].encode(), sys.argv[2].encode()
bindir = os.path.join(new_prefix.decode(), "bin")
for name in sorted(os.listdir(bindir)):
    path = os.path.join(bindir, name)
    if not os.path.isfile(path) or os.path.islink(path):
        continue
    with open(path, "rb") as fh:
        data = fh.read()
    marker = b"#!" + old_prefix
    if data.startswith(marker):
        with open(path, "wb") as fh:
            fh.write(b"#!" + new_prefix + data[len(marker):])
PY
fi
if [ "$made_backup" -eq 1 ]; then
  prune_backups
fi

# 5. Verify the final on-disk state (filesystem + launcher smoke, no activation).
[ -f "$DEST/$SKILL_NAME/SKILL.md" ] || fail "staged SKILL.md missing after swap"
# shellcheck disable=SC2086
for f in $SHIPPED_REFS; do
  [ -f "$DEST/$SKILL_NAME/references/$f" ] || fail "reference $f missing after swap"
done
# shellcheck disable=SC2086
for f in $SHIPPED_SCRIPTS; do
  [ -f "$DEST/$SKILL_NAME/scripts/$f" ] || fail "script $f missing after swap"
done
# Exactly one public skill entry may live directly under the destination:
# backups moved outside the root, so any second SKILL.md here is a real fault.
entries=0
for d in "$DEST"/*/; do
  [ -f "$d/SKILL.md" ] && entries=$((entries + 1))
done
[ "$entries" -eq 1 ] || fail "expected exactly one skill entry under $DEST, found $entries"
if [ "$SKIP_CORE" -eq 0 ]; then
  "$DEST/$SKILL_NAME/scripts/repo-audit" scan --list-checks >/dev/null \
    || fail "installed launcher probe failed"
  "$VENV/bin/python" "$VENV/bin/repo-audit" doctor >/dev/null 2>&1 \
    || echo "note: repo-audit doctor reports missing optional tools (run the installed launcher with doctor for details)" >&2
fi
echo "== done =="
