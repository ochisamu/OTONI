#!/usr/bin/env bash
set -euo pipefail
STUDIO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$STUDIO_ROOT"
mkdir -p vendor work models
REV="$(.venv/bin/python -c 'import json; print(json.load(open("diffsynth.lock.json"))["source"])')"
if [ ! -d vendor/DiffSynth-Studio/.git ]; then git clone https://github.com/modelscope/DiffSynth-Studio.git vendor/DiffSynth-Studio; fi
git -C vendor/DiffSynth-Studio checkout "$REV"
uv venv --allow-existing --python 3.12 .venv-diffsynth
uv pip install --python .venv-diffsynth/bin/python torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python .venv-diffsynth/bin/python -e 'vendor/DiffSynth-Studio[audio]' transformers==4.57.6 numpy==2.2.6 pydantic soundfile torchcodec==0.10.0 -c locks/diffsynth-constraints.txt
.venv/bin/python scripts/download_control_models.py diffsynth
.venv-diffsynth/bin/python -c 'from diffsynth.pipelines.diffsynth_music import DiffSynthMusicPipeline; import torch; assert torch.cuda.is_available()'
touch models/diffsynth-music/.ready
