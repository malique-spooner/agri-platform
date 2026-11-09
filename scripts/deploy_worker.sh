#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/agri-worker-deploy.XXXXXX")"
trap 'rm -rf "$stage_dir"' EXIT

cd "$repo_root"
uvx --from workers-py pywrangler sync
python3 scripts/build_worker_assets.py

cp app.py worker.py wrangler.jsonc "$stage_dir/"
cp -R database logic python_modules worker_assets "$stage_dir/"

cd "$stage_dir"
if [[ "${AGRI_DRY_RUN:-0}" == "1" ]]; then
  npx --yes wrangler deploy --dry-run
else
  npx --yes wrangler deploy
fi
