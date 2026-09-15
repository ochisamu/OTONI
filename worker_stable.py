"""Isolated, local Stable Audio 3 Medium instrumental generation."""
import json
import os
import sys
import time
from pathlib import Path
from schemas import SongInput
from stable_audio_support import ENGINE, music_prompt
from audio_storage import finalize_audio

def main():
    root=Path(__file__).resolve().parent;folder=Path(sys.argv[1]).resolve()
    request=SongInput.model_validate_json((folder/'input.json').read_text())
    if request.engine!=ENGINE:raise ValueError('Wrong worker')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    import soundfile as sf
    from stable_audio_3 import StableAudioModel
    from stable_audio_3.loading_utils import load_diffusion_cond
    checkpoint=root/'models/stable-audio-3-medium'
    config=json.loads((checkpoint/'resolved-config.json').read_text())
    print('STATUS Stable Audio 3 Mediumを読み込み中',flush=True)
    started=time.monotonic()
    model=load_diffusion_cond(config,str(checkpoint/'model.safetensors'),device='cuda',model_half=True)
    model.use_lora=False;model.lora_names=[]
    pipe=StableAudioModel(model,config,'cuda',True)
    print('STATUS インストを生成中',flush=True)
    prompt=music_prompt(request)
    audio=pipe.generate(prompt=prompt,duration=request.duration,seed=request.seed,steps=8,cfg_scale=1.0,
                        sample_size=config['sample_size'],batch_size=1,chunked_decode=True)
    samples=audio[0].detach().float().cpu().numpy().T
    if samples.ndim!=2 or samples.shape[1]!=2:raise RuntimeError('Invalid stereo output')
    sf.write(folder/'song.wav',samples,config['sample_rate'],subtype='PCM_24')
    (folder/'stable-request.json').write_text(json.dumps({'prompt':prompt,'duration':request.duration,'seed':request.seed,'steps':8,'cfg_scale':1.0},ensure_ascii=False,indent=2))
    storage=finalize_audio(folder,request.output_format,request.title,request.album_title,request.track_number)
    summary={'audio_seconds':storage['audio_seconds'],'sample_rate':storage['sample_rate'],'elapsed_seconds':round(time.monotonic()-started,2),'peak_vram_gib':round(torch.cuda.max_memory_allocated()/2**30,2),'tempo':{'requested_bpm':request.choices.bpm,'mode':'text_guidance','audio_bpm_verified':False}}
    (folder/'summary.json').write_text(json.dumps(summary,indent=2))
    print('STATUS 完了',flush=True)

if __name__=='__main__':
    from gpu_lock import gpu_lock
    with gpu_lock():main()
