#!/usr/bin/env bash
set -euo pipefail
STABLE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$STABLE_ROOT"
STABLE_REV="$(.venv/bin/python -c 'import json; print(json.load(open("stable.lock.json"))["source"])')"
if [ ! -d vendor/stable-audio-3/.git ]; then
  git clone https://github.com/Stability-AI/stable-audio-3.git vendor/stable-audio-3
fi
git -C vendor/stable-audio-3 checkout "$STABLE_REV"
if [ ! -x .venv-stable/bin/python ]; then uv venv .venv-stable --python .venv/bin/python; fi
uv pip install --python .venv-stable/bin/python torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv-stable/bin/python -e vendor/stable-audio-3 pydantic soundfile -c locks/stable-constraints.txt
.venv-stable/bin/python scripts/download_stable_models.py
