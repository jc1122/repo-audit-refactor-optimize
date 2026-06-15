#!/usr/bin/env bash
# One-line bootstrap: install the repo-audit family from scratch.
#   curl -fsSL https://raw.githubusercontent.com/jc1122/repo-audit-refactor-optimize/<tag>/bootstrap/install.sh | bash
set -euo pipefail

REPO_B_URL="https://github.com/jc1122/repo-audit-refactor-optimize.git"
REF="v0.12.0"            # SHIP CHECKLIST: bump to the new repo-B tag before tagging
DEST=""
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dest) DEST="$2"; shift 2;;
    --ref) REF="$2"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
if [ -z "$DEST" ]; then
  if [ -n "${AGENT_SKILLS_HOME:-}" ]; then DEST="$AGENT_SKILLS_HOME/skills"
  elif [ -n "${CODEX_HOME:-}" ]; then DEST="$CODEX_HOME/skills"
  else DEST="$HOME/.agents/skills"; fi
fi

run() { if [ "$DRY_RUN" -eq 1 ]; then echo "DRY: $*"; else eval "$*"; fi; }

echo "== repo-audit family bootstrap =="
echo "dest: $DEST"
echo "repo-audit-refactor-optimize @ $REF"

# 1. Install repo-B (the orchestrator) first.
TMPB="$(mktemp -d)"
run "git clone --depth 1 -b $REF $REPO_B_URL \"$TMPB\""
run "mkdir -p \"$DEST/repo-audit-refactor-optimize\""
run "git -C \"$TMPB\" archive $REF | tar -x -C \"$DEST/repo-audit-refactor-optimize\""

# 2. Read the manifest sources and install each at its pinned tag.
MANIFEST="$DEST/repo-audit-refactor-optimize/scripts/skill_bootstrap_manifest.json"
if [ "$DRY_RUN" -eq 1 ]; then MANIFEST="$(dirname "$0")/../scripts/skill_bootstrap_manifest.json"; fi
python3 - "$MANIFEST" "$DEST" "$DRY_RUN" <<'PY'
import json, subprocess, sys, tempfile, shlex
manifest, dest, dry = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
sources = json.load(open(manifest)).get("sources", {})
for sid, src in sources.items():
    url, tag, install = src["url"], src["tag"], src["install"]
    install = [a.replace("{dest}", dest) for a in install]
    print(f"source {sid} @ {tag}: {url}")
    if dry:
        print("DRY: git clone --depth 1 -b %s %s <tmp> && %s" % (tag, url, " ".join(install)))
        continue
    tmp = tempfile.mkdtemp()
    subprocess.check_call(["git", "clone", "--depth", "1", "-b", tag, url, tmp])
    subprocess.check_call(install, cwd=tmp)
PY

# 3. Verify (skip on dry-run).
if [ "$DRY_RUN" -eq 0 ]; then
  python3 "$DEST/repo-audit-refactor-optimize/scripts/check_skill_requirements.py" \
    --repo "$(mktemp -d)" --out-dir "$(mktemp -d)" | \
    python3 -c "import json,sys; d=json.load(sys.stdin); print('stop_before_discovery:', d.get('stop_before_discovery'))"
fi
echo "== done =="
