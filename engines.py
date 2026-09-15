"""Music engine metadata and isolated worker selection."""
import sys
from pathlib import Path

ACE_NAME = "ACE-Step 1.5 XL Turbo"
ACE_GUIDE_REVISION = "ca1e85fe9430179831e6bc6be790c332190a3866"
ACE_GUIDE_URL = f"https://github.com/ace-step/ACE-Step-1.5/blob/{ACE_GUIDE_REVISION}/docs/en/Tutorial.md"


def engine_status(root: Path):
    """Report readiness separately, so either engine can work without the other."""
    return {
        "diffsynth-music": {"label":"DiffSynth Music", "ready":(root/"models/diffsynth-music/.ready").is_file() and (root/".venv-diffsynth/bin/python").is_file(), "precision":"BF16 / CPU offload", "duration_min":10, "duration_max":180},
        "mulacover": {"label":"MuLaCover", "ready":(root/"models/mulacover/.ready").is_file() and (root/".venv-mulacover/bin/python").is_file(), "precision":"BF16 / lazy load", "reference_required":True, "noncommercial":True},
        "stable-audio-3-medium": {"label":"Stable Audio 3 Medium", "ready":
            (root/"models/stable-audio-3-medium/.ready").is_file() and (root/".venv-stable/bin/python").is_file(),
            "precision":"FP16 / chunked decode", "duration_min":10, "duration_max":180,
            "instrumental_only":True, "setup_url":"/static/stable-audio-setup.html"},
        "yue2": {"label": "YuE2-3B", "ready": all(
            (root / "models" / name / ".ready").is_file()
            for name in ("YuE2-3B", "YuE2-Vae")), "precision": "BF16 / VAE FP32"},
        "ace-xl-turbo": {"label": ACE_NAME, "ready": (
            (root / "models/ace/.ready").is_file()
            and (root / ".venv-ace/bin/python").exists()
            and (root / "vendor/ACE-Step-1.5/acestep/handler.py").is_file()),
            "precision": "BF16 / CPU offload", "duration_min": 10, "duration_max": 180},
    }


def worker_command(root: Path, engine: str, folder: Path):
    """Keep dependency sets and GPU lifetimes isolated while sharing one queue."""
    if engine in ("diffsynth-music", "mulacover"):
        environment = ".venv-diffsynth" if engine == "diffsynth-music" else ".venv-mulacover"
        return [str(root/environment/"bin/python"), "-u", str(root/"worker_control.py"), str(folder)]
    if engine == "stable-audio-3-medium":
        return [str(root / ".venv-stable/bin/python"), "-u", str(root / "worker_stable.py"), str(folder)]
    if engine == "ace-xl-turbo":
        return [str(root / ".venv-ace/bin/python"), "-u", str(root / "worker_ace.py"), str(folder)]
    return [sys.executable, "-u", str(root / "worker.py"), str(folder)]
