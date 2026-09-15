"""Validated lineage and immutable local snapshots for song derivatives."""
import json,os,shutil
from pathlib import Path
from fastapi import HTTPException
from audio_storage import stored_audio
from tempo_control import score_bpm


def source_files(root,jobs,request):
    if request.derivation_mode=='none':return None
    job=jobs.get(request.source_song_id)
    if not job or job.get('status')!='completed':
        raise HTTPException(400,'派生元には完成した曲を指定してください')
    folder=root/request.source_song_id
    if request.derivation_mode=='score':
        path=folder/'artifacts/score.abc'
        if not path.is_file():raise HTTPException(400,'この曲には引き継げるABC譜面がありません')
    else:
        name=stored_audio(folder)
        if not name:raise HTTPException(400,'派生元の音声がありません')
        path=folder/name
    return folder,path,job


def snapshot_source(folder,request,source):
    if source is None:return request
    origin,path,job=source
    record={'source_song_id':request.source_song_id,'source_title':job['title'],
            'mode':request.derivation_mode,'strength':request.reference_strength}
    if request.derivation_mode=='score':
        abc=path.read_text();(folder/'source-score.abc').write_text(abc)
        record['score_file']='source-score.abc'
        original=json.loads((origin/'input.json').read_text())
        request=request.model_copy(update={'abc':abc,'cot':'full','lyrics':original['lyrics']})
        bpm=score_bpm(abc)
        if bpm is not None and 40 <= bpm <= 220:
            request=request.model_copy(update={'choices':request.choices.model_copy(update={'bpm':bpm,'tempo':'auto'})})
    else:
        name='source-audio'+path.suffix
        try:os.link(path,folder/name)
        except OSError:shutil.copy2(path,folder/name)
        record['audio_file']=name
        if request.engine=='diffsynth-music' and request.control_mode=='vocals':
            original=json.loads((origin/'input.json').read_text())
            request=request.model_copy(update={'lyrics':original.get('lyrics','')})
    (folder/'derivation.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
    return request
