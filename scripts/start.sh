#!/usr/bin/env bash
set -euo pipefail
YUE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$YUE_ROOT"
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
exec .venv/bin/python -m uvicorn app:app --host "${YUE_HOST:-127.0.0.1}" --port "${YUE_PORT:-7860}"
