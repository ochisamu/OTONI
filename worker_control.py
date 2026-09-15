"""Isolated DiffSynth Music / MuLaCover generation on the shared GPU queue."""
import json,os,sys,time,subprocess,tempfile
from pathlib import Path
from schemas import SongInput
from language_policy import VOCAL_LANGUAGE_CODES
from audio_storage import finalize_audio


def source_audio(folder):
    meta=json.loads((folder/'derivation.json').read_text())
    path=(folder/meta['audio_file']).resolve()
    if not path.is_relative_to(folder.resolve()) or not path.is_file():raise ValueError('Invalid reference snapshot')
    return path


def run_diffsynth(root,folder,request):
    import torch,soundfile as sf
    from diffsynth.pipelines.diffsynth_music import DiffSynthMusicPipeline,ModelConfig
    from diffsynth.diffusion.template import TemplatePipeline
    from diffsynth.core.data.operators import LoadMultiTrackAudio
    from diffsynth.utils.music_tools import extract_prosody,generate_click
    models=root/'models/diffsynth-music'
    memory=dict(offload_dtype=torch.bfloat16,offload_device='cpu',onload_dtype=torch.bfloat16,onload_device='cpu',preparing_dtype=torch.bfloat16,preparing_device='cuda',computation_dtype=torch.bfloat16,computation_device='cuda')
    parts=['transformer','conditioner','text_encoder','vae']
    if request.control_mode in ('vocals','accompany','prosody'):parts.append('track_separator')
    configs=[]
    for part in parts:
        config=memory.copy()
        if part=='track_separator':
            for key in ['offload_dtype','onload_dtype','preparing_dtype','computation_dtype']:config[key]=torch.float32
        configs.append(ModelConfig(path=str(models/part/'model.safetensors'),**config))
    pipe=DiffSynthMusicPipeline.from_pretrained(torch_dtype=torch.bfloat16,device='cuda',model_configs=configs,tokenizer_config=ModelConfig(path=str(models/'text_encoder')),vram_limit=11 if request.control_mode=='native' else 5)
    # The upstream DiT concatenates this small root parameter directly before wrapped layers.
    # Keep it on the compute device while the large layers use official CPU offload.
    pipe.dit.placeholder_audio.data = pipe.dit.placeholder_audio.data.to('cuda')
    template=TemplatePipeline.from_pretrained(torch_dtype=torch.bfloat16,device='cuda',lazy_loading=True,model_configs=[ModelConfig(path=str(models/p)) for p in ['template_control','template_prosody','template_reference']])
    mode=request.control_mode
    kwargs=dict(prompt=request.style,negative_prompt=pipe.default_negative_prompt,lyrics='' if request.choices.vocal=='instrumental' else request.lyrics,duration=request.duration,seed=request.seed,tiled=True,cfg_scale=4,num_inference_steps=50,bpm=request.choices.bpm,vocal_language='unknown' if request.choices.vocal=='instrumental' else VOCAL_LANGUAGE_CODES[request.language])
    if mode=='beats':
        bpm=request.choices.bpm or 120;beats=generate_click(bpm,duration=request.duration)
        kwargs.update(bpm=bpm,template_inputs=[{'model_id':0,'audio':beats}],negative_template_inputs=[{'model_id':0,'audio':beats*0}])
    elif mode!='native':
        audio=LoadMultiTrackAudio(division_factor=3840)(str(source_audio(folder)))
        # Bound conditioning length to the requested output budget.
        audio=audio[:,:int(request.duration*48000)]
        if mode=='reference':
            kwargs.update(template_inputs=[{'model_id':2,'audio':audio}],num_inference_steps=100)
        else:
            track=['drums','bass','other'] if mode=='accompany' else 'vocals'
            ref=pipe.extract_track(audio,track=track)
            if mode=='prosody':ref=extract_prosody(ref)
            mid=1 if mode=='prosody' else 0
            kwargs.update(duration=ref.shape[1]/48000,template_inputs=[{'model_id':mid,'audio':ref}],negative_template_inputs=[{'model_id':mid,'audio':ref}])
            if mode!='prosody':kwargs.update(target_audio=ref,target_track=track)
            if mode=='vocals':kwargs['lyrics']=''
    print('STATUS DiffSynth Musicで音声生成中',flush=True)
    audio=template(pipe,**kwargs)
    sf.write(folder/'song.wav',audio.detach().float().cpu().numpy().T,48000,subtype='PCM_24')


def run_mulacover(root,folder,request):
    import torch
    from mulacover import MuLaCoverGenPipeline
    torch.manual_seed(request.seed)
    pipe=MuLaCoverGenPipeline.from_pretrained(str(root/'models/mulacover'),device=torch.device('cuda'),dtype={'mulacover':torch.bfloat16,'codec':torch.float32,'qwen':torch.float32,'transcriptor':torch.float32},lazy_load=True)
    # Pass paths for text so a user-provided string can never be treated as a local file path.
    lyrics=folder/'control-lyrics.txt';tags=folder/'control-style.txt'
    lyrics.write_text(request.lyrics);tags.write_text(request.style)
    print('STATUS 元音源からメロディー・コードを抽出しMuLaCoverで生成中',flush=True)
    with tempfile.TemporaryDirectory(prefix='reference-',dir=folder) as temp:
        reference=Path(temp)/'reference.wav'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(source_audio(folder)),'-t',str(request.duration),'-ar','44100','-ac','2',str(reference)],check=True)
        pipe({'ref_audio':str(reference),'lyrics':str(lyrics),'tags':str(tags),'bpm':request.choices.bpm},save_path=str(folder/'song.wav'),symbolic_save_dir=str(folder/'symbolic'),max_audio_length_ms=request.duration*1000,temperature=1.0,topk=250,cfg_scale=1.5)


def main():
    root=Path(__file__).resolve().parent;folder=Path(sys.argv[1]).resolve()
    request=SongInput.model_validate_json((folder/'input.json').read_text())
    os.environ['DIFFSYNTH_SKIP_DOWNLOAD']='True';os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import torch
    start=time.monotonic()
    if request.engine=='diffsynth-music':run_diffsynth(root,folder,request)
    elif request.engine=='mulacover':run_mulacover(root,folder,request)
    else:raise ValueError('Wrong worker engine')
    storage=finalize_audio(folder,request.output_format,request.title,request.album_title,request.track_number)
    summary={'audio_seconds':storage['audio_seconds'],'sample_rate':storage['sample_rate'],'elapsed_seconds':round(time.monotonic()-start,2),'peak_vram_gib':round(torch.cuda.max_memory_allocated()/2**30,2),'control_mode':request.control_mode,'conditioning_bpm':(request.choices.bpm or 120) if request.control_mode=='beats' else request.choices.bpm,'tempo':{'requested_bpm':request.choices.bpm,'audio_bpm_verified':False},'model_lock':json.loads((root/('diffsynth.lock.json' if request.engine=='diffsynth-music' else 'mulacover.lock.json')).read_text())}
    (folder/'artifacts').mkdir(exist_ok=True)
    (folder/'artifacts/result.json').write_text(json.dumps(summary,indent=2))
    (folder/'summary.json').write_text(json.dumps(summary,indent=2));print('STATUS 完了',flush=True)

if __name__=='__main__':
    from gpu_lock import gpu_lock
    with gpu_lock():main()
