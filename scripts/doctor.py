"""Read-only environment diagnostics; never read credentials or dump environment variables."""
import json
import platform
import shutil
import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
report={'platform':platform.system(),'kernel':platform.release(),'tools':{x:bool(shutil.which(x)) for x in ('uv','git','ffmpeg','ffprobe','codex','nvidia-smi')},'japanese_font':Path('/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf').is_file()}
if shutil.which('nvidia-smi'):
    r=subprocess.run(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],capture_output=True,text=True,timeout=15)
    report['gpu']=r.stdout.strip() if r.returncode==0 else 'nvidia-smi failed'
report['environments']={}
for env in ('.venv','.venv-ace','.venv-stable','.venv-diffsynth','.venv-mulacover'):
    py=root/env/'bin/python'
    if not py.exists():report['environments'][env]='not installed';continue
    r=subprocess.run([str(py),'-c','import json,sys,importlib.metadata as m; print(json.dumps({"python":sys.version.split()[0],"torch":m.version("torch")}))'],capture_output=True,text=True,timeout=15)
    report['environments'][env]=json.loads(r.stdout) if r.returncode==0 else 'incomplete environment'
report['model_markers']={name:(root/'models'/name/'.ready').exists() for name in ('YuE2-3B','YuE2-Vae','ace','stable-audio-3-medium','diffsynth-music','mulacover')}
print(json.dumps(report,ensure_ascii=False,indent=2))
