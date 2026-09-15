# OTONI

**English** | [日本語](README.ja.md)

A local music creation workspace: develop an idea, generate music on your GPU, and listen to it as an album. OTONI brings YuE2, ACE-Step, and Stable Audio into one library. It is a **music generation assistance tool**, not a music generation model: it helps prepare inputs, run models, and manage their outputs.

**An experimental personal application for Windows + WSL2 + an NVIDIA GPU.** Audio generation runs locally. Codex-assisted lyrics, arrangements, reference research, and cover artwork require an internet connection and a ChatGPT login for Codex. These assistance features do not run offline. The application UI and most detailed guides are currently in Japanese; this English README does not change the UI language.

## Features

- Generate individual tracks or albums, including albums that use different models for different tracks
- Set genre, BPM, vocals, and duration; use Codex to draft prompts tailored to each model
- Lyrics in Japanese, English, Chinese, or primarily Japanese with short English phrases
- Instrumental tracks, variations of your generated music, and readable lyrics and generation settings
- M4A/FLAC storage, a shared player, shuffle, mobile layouts, and dark mode
- YouTube-ready album videos with cover artwork and track titles that change with the music; optional YouTube upload integration

## Models and application limits

| Model | Use in OTONI | Duration controls | Environment |
|---|---|---|---|
| YuE2-3B | Vocals, experimental instrumentals, ABC score planning | Approximate arrangement target; no exact duration guarantee | `.venv` |
| ACE-Step 1.5 XL Turbo | Vocals, instrumentals, audio-based variations | Fixed 10–180 seconds / automatic 30–180 seconds | `.venv-ace` |
| Stable Audio 3 Medium | Instrumentals only | Fixed 10–180 seconds / automatic 30–180 seconds | `.venv-stable` |
| DiffSynth Music | Native generation, beats and audio conditioning | Fixed 10–180 seconds / automatic 30–180 seconds | `.venv-diffsynth` |
| MuLaCover | Covers from completed library tracks | 10–180 second generation ceiling | `.venv-mulacover` |

These are application limits, not the models' maximum capabilities. All models share a GPU queue and run **one track at a time**. Requested BPM, vocal character, genre, and lyrics are not guaranteed to match the generated audio exactly.

## Getting started

Tested on **WSL2, Ubuntu 22.04, RTX 5060 Ti 16GB, Windows NVIDIA driver 591.86, and Python 3.12.11**. macOS, AMD GPUs, CPU-only audio generation, and native Windows execution have not been tested. Minimum VRAM requirements for other GPUs have not been established.

Use the WSL Linux filesystem, for example `~/workspace/OTONI`. Install the OS packages and [uv](https://docs.astral.sh/uv/getting-started/installation/) first:

```bash
sudo apt update
sudo apt install -y git curl ffmpeg fonts-ipafont-gothic
# Install uv using its official instructions before continuing.
nvidia-smi

git clone https://github.com/ochisamu/OTONI.git
cd OTONI
cp .env.example .env
./scripts/setup.sh
./scripts/start.sh
```

The setup installs the shared environment **and YuE2**. Currently this shared YuE2 environment is also required when you only intend to use ACE-Step or Stable Audio. The instructions do not install a separate Linux display driver inside WSL.

Open **http://localhost:7860**. Keep the terminal open; press Ctrl+C to stop. Do not overwrite an existing `.env` when updating an installation.

For a first GPU check without Codex, open single-track creation, disable automatic Codex assistance, load the English song sample, and generate with YuE2. Automatic album planning requires Codex.

### Additional models

After the shared setup:

```bash
# ACE-Step 1.5 XL Turbo, in its own environment
./scripts/setup_ace.sh

# Stable Audio: first accept the model's access conditions on Hugging Face,
# then sign in using the shared environment's CLI.
.venv/bin/hf auth login
./scripts/setup_stable.sh
```

Accept access conditions at the [official Stable Audio model page](https://huggingface.co/stabilityai/stable-audio-3-medium) using the same account as the CLI. Enter tokens interactively; do not put them in source files or Issues. Stable Audio uses the local Medium model, not the Large cloud API. Refresh the page after installing a model.

### Codex assistance

Install a Linux/WSL-compatible Codex using the [official setup instructions](https://learn.chatgpt.com/docs/quickstart). Verify `codex --version` and `codex app-server --help`. If it is not on PATH, set `YUE_CODEX_BIN` in `.env` to the executable's absolute path. Use the connection button at the top of the app to sign in with ChatGPT. OTONI uses Codex App Server; API-key-based songwriting is not implemented.

Prompts, lyrics, styles, and reference descriptions are sent to Codex and consume its usage allowance. Available models, web search, and cover generation depend on your Codex version and account. The tested CLI version is `0.154.0-alpha.6.2`; compatibility with every public CLI release is not guaranteed. See the official [authentication](https://learn.chatgpt.com/docs/auth) and [App Server](https://learn.chatgpt.com/docs/app-server) documentation.

### Background operation

If WSL user systemd is available:

```bash
./scripts/service.sh start
./scripts/service.sh status
./scripts/service.sh logs
# Wait for generation to finish before restarting or stopping.
./scripts/service.sh restart
./scripts/service.sh stop
```

The script generates and enables a user service for the current checkout. The unit retains the name `yue2-studio.service`. WSL startup and user service startup depend on your system configuration. To disable automatic service startup, run `systemctl --user disable --now yue2-studio.service`. Without user systemd, use `./scripts/start.sh`.

### Launch and generate your first track

Run these commands in the checkout directory after setup (stop any foreground instance with Ctrl+C first):

```bash
# In a new terminal, navigate to wherever you cloned OTONI, for example:
cd ~/workspace/OTONI
./scripts/start.sh
```

If you cloned elsewhere, use that path. Once the terminal reports that Uvicorn is running, open **http://localhost:7860** in your Windows browser. Keep this terminal open. Use either this foreground command or the systemd service above, not both at once.

1. Open **曲をつくる** (create music) and select an installed model.
2. For a first YuE2 test, load the English sample and turn off **生成前にCodexでメロディー・構成を整える** (automatic Codex assistance). This path does not require ChatGPT login.
3. Click **曲を生成** (generate). Generation is queued and runs one track at a time; the first run may take longer while the model loads.
4. Open **すべての曲** (all tracks). When the track is complete, play it or open its details to inspect lyrics and settings.

For assisted songwriting or automatic albums, connect ChatGPT first and enable assistance. For Stable Audio, select instrumental generation; it does not generate sung lyrics through this app.

Stop a foreground server with **Ctrl+C**, preferably after generation finishes. To stop a background service, use `./scripts/service.sh stop`. To launch again, repeat the corresponding start command. Closing only the browser does not stop the server or its queue.

See the [setup guide (Japanese)](docs/SETUP.md) for LAN access, YouTube setup, and troubleshooting.

## Storage and reproducibility

Expect tens of gigabytes for models, environments, and download caches. Approximate model storage is 7.3GB for YuE2, an additional 21GB for ACE-Step, and an additional 9.8GB for Stable Audio. Python environments, caches, tracks, and videos need more space. DiffSynth adds approximately 34GB and MuLaCover with its supporting models approximately 17GB. For all five models, plan around 150–200GB of free space as a rough starting point and check actual usage, especially download caches.

Model/source revisions and dependency records are included in `*.lock.json`, `locks/`, and `vendor/SHA256SUMS`. The [reproducibility guide (Japanese)](docs/REPRODUCIBILITY.md) describes how each setup uses them and what remains unverified.

Audio generation has been verified on the development machine. **A complete clean installation and GPU generation on another PC have not been verified.** The application tests run without model weights or credentials. Passing those tests does not establish GPU compatibility or musical quality.

To run the application tests without GPU dependencies, install FFmpeg and the IPA fonts above, then:

```bash
uv venv --python 3.12 .venv-test
uv pip install --python .venv-test/bin/python -r requirements-test.txt
.venv-test/bin/python -m pytest -q
```

`python3 scripts/doctor.py` reports basic environment information without reading credentials. To compare audio generation, reuse the saved `input.json` and seed with automatic assistance disabled. Re-running Codex can change the prompt, lyrics, and duration. Different hardware, kernels, dependencies, or model revisions may produce different audio even with the same seed.

## Data and connections

Audio, lyrics, and settings normally live in `data/`, models in `models/`, and temporary files in `work/`. None are included in the repository. Back up `data/`, not just the audio files; it can also contain private YouTube connection information. After validating M4A/FLAC conversion, OTONI removes redundant WAV files. Deletion has no undo.

LAN access is optional. OTONI does not provide multi-user authentication or per-user permissions and is not intended to be exposed directly to the public internet. See [connections and data (Japanese)](docs/SECURITY.md).

## License and model terms

OTONI's own code is available under the **[MIT License](LICENSE)**.

**Consult each model's official license, model card, and accompanying notices for its terms of use.** Model weights, inference wheels, and external repositories are not bundled; setup retrieves them from their official sources. References are listed in [third-party notices (Japanese)](THIRD_PARTY_NOTICES.md).

OTONI does not grant blanket permission or guarantees for publishing or commercially using generated music. Check the applicable model and service terms and the rights associated with your inputs and outputs. This also does not mean that every model license automatically applies unchanged to its outputs. OTONI's MIT license is separate from those terms.

## Development and reports

[Contributing (Japanese)](CONTRIBUTING.md) · [Release checklist (Japanese)](docs/RELEASE.md)

For bug reports, include your OS, GPU, selected model, and steps to reproduce the error. Do not attach `.env`, authentication files, or entire folders of personal lyrics and generated music.

## DiffSynth Music / MuLaCover

DiffSynth Music adds native generation and audio conditioning; MuLaCover adds covers from library tracks. See [setup, usage and model terms](docs/CONTROL_MODELS.md).
