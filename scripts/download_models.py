"""Download only inference assets, pin upstream revisions, verify official hashes."""
import hashlib
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
lock_path = ROOT / "models.lock.json"
lock = json.loads(lock_path.read_text()) if lock_path.exists() else {}
patterns = ["config.json", "generation_config.json", "yue2_generation_config.json",
            "weights_manifest.json", "*.safetensors", "*.safetensors.index.json",
            "qwen.tiktoken", "LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/*"]
for name in ("YuE2-3B", "YuE2-Vae"):
    repo = f"m-a-p/{name}"
    revision = lock.get(repo) or HfApi().model_info(repo).sha
    lock[repo] = revision
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    dest = ROOT / "models" / name
    print(f"Downloading {repo}@{revision}", flush=True)
    snapshot_download(repo, revision=revision, local_dir=dest, allow_patterns=patterns, max_workers=3)
    manifest = dest / "weights_manifest.json"
    if manifest.exists():
        for filename, expected in json.loads(manifest.read_text())["files"].items():
            digest = hashlib.file_digest(open(dest / filename, "rb"), "sha256").hexdigest()
            if digest != expected["sha256"]:
                raise RuntimeError(f"Checksum mismatch: {filename}")
    (dest / ".ready").write_text(revision + "\n")
    print(f"Verified {name}", flush=True)
