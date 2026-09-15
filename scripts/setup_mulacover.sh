#!/usr/bin/env bash
set -euo pipefail
STUDIO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$STUDIO_ROOT"
mkdir -p vendor work models
REV="$(.venv/bin/python -c 'import json; print(json.load(open("mulacover.lock.json"))["source"])')"
if [ ! -d vendor/MuLaCover/.git ]; then git clone https://github.com/HeartMuLa/MuLaCover.git vendor/MuLaCover; fi
git -C vendor/MuLaCover checkout "$REV"
uv venv --allow-existing --python 3.10 .venv-mulacover
uv pip install --python .venv-mulacover/bin/python torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv-mulacover/bin/python -e 'vendor/MuLaCover[audio]' pydantic pyarrow==20.0.0 -c locks/mulacover-constraints.txt
.venv/bin/python scripts/download_control_models.py mulacover
.venv-mulacover/bin/python -c 'from mulacover import MuLaCoverGenPipeline; import torch; assert torch.cuda.is_available()'
touch models/mulacover/.ready
