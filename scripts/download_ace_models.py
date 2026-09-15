"""Download the exact XL Turbo and shared inference assets, verifying HF hashes."""
import hashlib
import json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
lock = json.loads((ROOT / "ace.lock.json").read_text())
checkpoints = ROOT / "models/ace"
checkpoints.mkdir(parents=True, exist_ok=True)
(checkpoints / ".ready").unlink(missing_ok=True)
for repo, patterns, dest in [
    ("ACE-Step/acestep-v15-xl-turbo", ["*"], checkpoints / "acestep-v15-xl-turbo"),
    ("ACE-Step/Ace-Step1.5", ["vae/*", "Qwen3-Embedding-0.6B/*"], checkpoints),
]:
    revision = lock[repo]
    print(f"Downloading {repo}@{revision}", flush=True)
    snapshot_download(repo, revision=revision, local_dir=dest,
                      allow_patterns=patterns, max_workers=3)
    info = HfApi().model_info(repo, revision=revision, files_metadata=True)
    import fnmatch
    for entry in info.siblings:
        if not any(fnmatch.fnmatch(entry.rfilename, p) for p in patterns):
            continue
        path = dest / entry.rfilename
        if not path.is_file() or path.stat().st_size != entry.size:
            raise RuntimeError(f"Incomplete download: {path}")
        if entry.lfs:
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != entry.lfs.sha256:
                raise RuntimeError(f"Checksum mismatch: {path}")
    print(f"Verified {repo}", flush=True)
(checkpoints / ".ready").write_text(json.dumps(lock, indent=2) + "\n")
