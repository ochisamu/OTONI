"""Pinned official control-model assets; credentials remain with Hugging Face."""
import argparse,hashlib,json,shutil,urllib.request
from pathlib import Path
from huggingface_hub import snapshot_download,hf_hub_download
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('engine',choices=['diffsynth','mulacover']);args=p.parse_args()
lock=json.loads((ROOT/(args.engine+'.lock.json')).read_text())
for repo,info in lock['models'].items():
 folder=ROOT/'models'/info['directory'];folder.mkdir(parents=True,exist_ok=True)
 snapshot_download(repo,revision=info['revision'],local_dir=folder,ignore_patterns=['assets/*','.gitattributes'],max_workers=3)
 if repo=='HeartMuLa/MuLaCover':
  for line in (folder/'SHA256SUMS').read_text().splitlines():
   if not line.strip():continue
   expected,name=line.split(maxsplit=1);name=name.lstrip('*')
   path=(folder/name).resolve()
   if not path.is_relative_to(folder.resolve()):raise ValueError('Invalid checksum path')
   with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
   if actual!=expected:raise ValueError('Model checksum mismatch: '+name)
if args.engine=='mulacover':
 folder=ROOT/'models/mulacover/SymbolicTranscriptor';(folder/'yourmt3').mkdir(parents=True,exist_ok=True);(folder/'chord').mkdir(exist_ok=True)
 info=lock['transcriptor'];source=hf_hub_download(info['repo'],info['file'],repo_type='space',revision=info['revision'])
 shutil.copyfile(source,folder/'yourmt3/last.ckpt')
 for fold in range(5):
  name=f'joint_chord_net_ismir_naive_v1.0_reweight(0.0,10.0)_s{fold}.best.sdict'
  url='https://raw.githubusercontent.com/music-x-lab/ISMIR2019-Large-Vocabulary-Chord-Recognition/'+lock['chord_revision']+'/cache_data/'+name
  dest=folder/'chord'/name;tmp=dest.with_suffix('.tmp')
  with urllib.request.urlopen(url) as response,tmp.open('wb') as output:shutil.copyfileobj(response,output)
  tmp.replace(dest)
print('Pinned assets downloaded; runtime validation is required before readiness.',flush=True)
