#!/usr/bin/env bash
set -euo pipefail
YUE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$YUE_ROOT"
command -v uv >/dev/null || { echo 'uv is required: https://docs.astral.sh/uv/getting-started/installation/'; exit 1; }
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || { echo 'ffmpeg/ffprobe are required: sudo apt install ffmpeg'; exit 1; }
mkdir -p vendor work models data
uv venv --python 3.12 --allow-existing .venv
if [ ! -f vendor/yue2_infer-0.1.5-py3-none-any.whl ]; then
  curl --fail --location --retry 3 https://huggingface.co/m-a-p/YuE2-3B/resolve/29b3558dd46954a0cd9021dc76d5c91864a0f1c7/yue2_infer-0.1.5-py3-none-any.whl -o vendor/yue2_infer-0.1.5-py3-none-any.whl
fi
sha256sum --check vendor/SHA256SUMS
uv pip install --python .venv/bin/python torch==2.10.0 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv/bin/python -r requirements.txt -c locks/yue2-constraints.txt
.venv/bin/python scripts/download_models.py
.venv/bin/python -c 'import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name())'
echo 'Ready. Start with ./scripts/start.sh, then open http://localhost:7860'
