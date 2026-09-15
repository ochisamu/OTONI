"""Download only the official, access-controlled model after the user accepts its terms."""
import json
from pathlib import Path
from huggingface_hub import snapshot_download
ROOT=Path(__file__).resolve().parents[1]
lock=json.loads((ROOT/'stable.lock.json').read_text())
repo=lock['model']
folder=ROOT/'models/stable-audio-3-medium'
folder.mkdir(parents=True,exist_ok=True)
try:
    revision=lock['revision']
    snapshot_download(repo,revision=revision,local_dir=folder,
        allow_patterns=['*.json','*.safetensors','*.model','*.txt','LICENSE*','README.md'])
    config=json.loads((folder/'model_config.json').read_text())
    found=False
    for c in config['model']['conditioning']['configs']:
        if c['type']!='t5gemma':continue
        found=True
        cfg=c['config'];subfolder=cfg.get('subfolder') or 'text_encoder'
        encoder=(folder/subfolder).resolve()
        if not encoder.is_relative_to(folder.resolve()):raise RuntimeError('Unexpected encoder path')
        if not (encoder/'config.json').is_file():
            raise RuntimeError('Bundled T5Gemma encoder was not found; inspect official model config before continuing')
        cfg['model_path']=str(encoder);cfg.pop('subfolder',None)
    if not found:raise RuntimeError('Expected T5Gemma configuration was not found')
    (folder/'resolved-config.json').write_text(json.dumps(config,indent=2))
    if not (folder/'model.safetensors').is_file():raise RuntimeError('Missing checkpoint')
    (folder/'snapshot.json').write_text(json.dumps({'repo':repo,'revision':revision},indent=2))
    from stable_audio_3 import StableAudioModel
    (folder/'.ready').write_text(revision)
    print('Stable Audio 3 Medium models ready')
except Exception as exc:
    (folder/'.ready').unlink(missing_ok=True)
    print('Official model setup incomplete:',type(exc).__name__)
    print('Accept access conditions at https://huggingface.co/stabilityai/stable-audio-3-medium and run .venv-stable/bin/hf auth login, then retry.')
    raise SystemExit(1)
