"""Export only reviewed source files, with a hash manifest and basic privacy checks."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def export(output):
    output=output.resolve()
    if output.exists():raise ValueError('Output already exists; choose a new directory')
    files=[]
    for name in (ROOT/'release-files.txt').read_text().splitlines():
        if not name or name.startswith('#'):continue
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Invalid release path')
        p=ROOT/name
        if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(ROOT):
            raise ValueError('Invalid release path: '+name)
        if len(p.read_bytes())>2_000_000:raise ValueError('Unexpected large file: '+name)
        text=p.read_bytes().decode('utf-8',errors='ignore')
        patterns=[r'hf_[A-Za-z0-9]{20,}',r'sk-[A-Za-z0-9_-]{24,}',r'gh[pousr]_[A-Za-z0-9]{20,}',r'-----BEGIN [A-Z ]*PRIVATE KEY-----',r'/home/'+'ikai/',r'/mnt/c/[Uu]sers/'+'ikai/']
        if any(re.search(pattern,text) for pattern in patterns):raise ValueError('Review sensitive content in: '+name)
        files.append((name,p))
    output.mkdir(parents=True)
    manifest={}
    for name,p in files:
        dest=output/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        manifest[name]=hashlib.sha256(dest.read_bytes()).hexdigest()
    (output/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Exported {len(files)} reviewed files; manifest written.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    export(parser.parse_args().output)
