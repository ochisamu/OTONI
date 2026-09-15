"""Install the optional LM from the same pinned release as the shared ACE assets."""
import hashlib,json,sys
from pathlib import Path
from huggingface_hub import HfApi,snapshot_download
ROOT=Path(__file__).resolve().parents[1]
lock=json.loads((ROOT/'ace.lock.json').read_text())
repo='ACE-Step/Ace-Step1.5';rev=lock[repo];prefix='acestep-5Hz-lm-1.7B/'
folder=ROOT/'models/ace'
snapshot_download(repo,revision=rev,local_dir=folder,allow_patterns=[prefix+'*'],max_workers=2)
info=HfApi().model_info(repo,revision=rev,files_metadata=True)
for f in info.siblings:
    if not f.rfilename.startswith(prefix):continue
    p=folder/f.rfilename
    assert p.stat().st_size==f.size
    if f.lfs:
        with p.open('rb') as stream: assert hashlib.file_digest(stream,'sha256').hexdigest()==f.lfs.sha256
(folder/prefix/'.ready').write_text(json.dumps({'repo':repo,'revision':rev}))
print('LM 1.7B downloaded and verified',flush=True)
