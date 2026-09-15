#!/usr/bin/env bash
set -euo pipefail
ACE_STUDIO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ACE_STUDIO_ROOT"
command -v uv >/dev/null || { echo 'uv is required'; exit 1; }
ACE_SOURCE_REV="$(.venv/bin/python -c 'import json; print(json.load(open("ace.lock.json"))["source"])')"
if [ ! -d vendor/ACE-Step-1.5/.git ]; then
  git clone https://github.com/ace-step/ACE-Step-1.5.git vendor/ACE-Step-1.5
fi
git -C vendor/ACE-Step-1.5 checkout "$ACE_SOURCE_REV"
cd vendor/ACE-Step-1.5
UV_PROJECT_ENVIRONMENT="$ACE_STUDIO_ROOT/.venv-ace" uv sync --frozen --python "$ACE_STUDIO_ROOT/.venv/bin/python"
cd "$ACE_STUDIO_ROOT"
.venv/bin/python scripts/download_ace_models.py
.venv-ace/bin/python -c 'import torch; from acestep.handler import AceStepHandler; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name())'
echo 'ACE-Step 1.5 XL Turbo ready. Restart the studio and select the model.'
