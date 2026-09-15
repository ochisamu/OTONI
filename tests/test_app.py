import asyncio
import json
import pytest
from fastapi.testclient import TestClient
import app as service
from schemas import SongInput, MusicChoices

HEADERS = {"X-Yue-Request": "studio"}
INPUT = {"title": "Test", "style": "Acoustic pop", "lyrics": "[Verse]\nA new day"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("YuE2-3B", "YuE2-Vae"):
        p = tmp_path / "models" / name
        p.mkdir(parents=True)
        (p / ".ready").touch()
    data = tmp_path / "songs"
    data.mkdir()
    monkeypatch.setattr(service, "ROOT", tmp_path)
    monkeypatch.setattr(service, "JOBS", data)
    monkeypatch.setattr(service, "jobs", {})
    monkeypatch.setattr(service, "queue", asyncio.Queue())
    monkeypatch.setattr(service, "active", None)
    monkeypatch.setattr(service, "preparation", None)
    return TestClient(service.app)


def test_input_validation():
    for update in ({"lyrics":" "}, {"cfg_scale":float('nan')}, {"seed":-1},
                   {"max_tokens":100000}, {"cot":"off","abc":"X:1"}, {"output":"/tmp/escape"}):
        with pytest.raises(ValueError):
            SongInput(**{**INPUT, **update})


def test_cross_origin_and_missing_header_are_blocked(client):
    assert client.post('/api/songs', json=INPUT).status_code == 403
    assert client.post('/api/songs', json=INPUT, headers={**HEADERS, 'Origin':'https://evil.example'}).status_code == 403
    assert client.get('/api/songs', headers={'Host':'evil.example'}).status_code == 400


def test_persist_queue_limit_and_cancel(client):
    for i in range(4):
        response=client.post('/api/songs', json=INPUT, headers=HEADERS)
        assert response.status_code == 202
    assert client.post('/api/songs', json=INPUT, headers=HEADERS).status_code == 429
    jid=response.json()['id']
    assert json.loads((service.JOBS/jid/'input.json').read_text())['lyrics']==INPUT['lyrics']
    assert client.post(f'/api/songs/{jid}/cancel', json={}, headers=HEADERS).json()['status']=='cancelled'
    assert client.post(f'/api/songs/{jid}/cancel', json={}, headers=HEADERS).status_code==409
    assert client.post('/api/songs', json=INPUT, headers=HEADERS).status_code == 202


def test_downloads_are_whitelisted_and_completed_only(client):
    jid=client.post('/api/songs', json=INPUT, headers=HEADERS).json()['id']
    assert client.get(f'/api/songs/{jid}/file/input.json').status_code==200
    assert client.get(f'/api/songs/{jid}/file/job.json').status_code==404
    assert client.get(f'/api/songs/{jid}/file/song.wav').status_code==404
    assert client.get('/api/songs/not-found').status_code==404
    assert client.get(f'/api/songs/{jid}').json()['input']['style']==INPUT['style']


def test_not_ready_returns_clear_error(client):
    (service.ROOT/'models/YuE2-3B/.ready').unlink()
    assert client.post('/api/songs', json=INPUT, headers=HEADERS).status_code == 503


def make_ace_ready():
    for name in ('models/ace/.ready', '.venv-ace/bin/python',
                 'vendor/ACE-Step-1.5/acestep/handler.py'):
        path = service.ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()


def test_engine_readiness_is_independent_and_inputs_persist(client):
    ace = {**INPUT, 'engine': 'ace-xl-turbo', 'duration': 90}
    assert client.post('/api/songs', json=ace, headers=HEADERS).status_code == 503
    make_ace_ready()
    (service.ROOT / 'models/YuE2-3B/.ready').unlink()
    result = client.post('/api/songs', json=ace, headers=HEADERS)
    assert result.status_code == 202
    job = client.get('/api/songs/' + result.json()['id']).json()
    assert job['engine'] == 'ace-xl-turbo' and job['input']['duration'] == 90
    assert client.post('/api/songs', json=INPUT, headers=HEADERS).status_code == 503


@pytest.mark.parametrize('update', [{'duration': 0}, {'duration': 181},
    {'abc': 'X:1'}, {'cfg_scale': 1.2}, {'lyrics': 'a' * 4097}, {'engine': 'ace-standard'}])
def test_ace_rejects_unsupported_controls(update):
    with pytest.raises(ValueError):
        SongInput(**{**INPUT, 'engine': 'ace-xl-turbo', **update})


def test_ace_assistance_receives_engine_duration_and_preserves_instrumental(client, monkeypatch):
    async def fake(request):
        assert request.engine == 'ace-xl-turbo' and request.duration == 120
        assert request.preserve_lyrics is False
        assert request.choices.vocal == 'instrumental'
        return {'title': 'Piano', 'style': 'Instrumental piano jazz', 'lyrics': 'discard sung words'}
    monkeypatch.setattr(service.bridge, 'compose', fake)
    make_ace_ready()
    request = SongInput(engine='ace-xl-turbo', duration=120, auto_assist=True,
                        choices=MusicChoices(vocal='instrumental'))
    job = client.post('/api/songs', json=request.model_dump(), headers=HEADERS).json()
    result = asyncio.run(service.prepare_song(service.JOBS / job['id'], request))
    assert result.lyrics == '[Instrumental]' and result.engine == 'ace-xl-turbo'
    assert result.duration == 120 and not result.auto_assist


def test_mixed_queue_routes_to_isolated_workers(client, monkeypatch):
    async def scenario():
        make_ace_ready()
        commands = []
        class Process:
            returncode = 0
            async def wait(self):
                return 0
        async def launch(*args, **kwargs):
            from pathlib import Path
            commands.append(args)
            folder = Path(args[-1])
            (folder / 'summary.json').write_text(json.dumps({'audio_seconds': 1}))
            return Process()
        monkeypatch.setattr(service.asyncio, 'create_subprocess_exec', launch)
        for engine in ('ace-xl-turbo', 'yue2'):
            await service.create_song(SongInput(**INPUT, engine=engine))
        task = asyncio.create_task(service.run_queue())
        try:
            await asyncio.wait_for(service.queue.join(), 2)
            assert commands[0][0].endswith('.venv-ace/bin/python')
            assert commands[0][2].endswith('worker_ace.py')
            assert commands[1][2].endswith('/worker.py')
            assert all(j['status'] == 'completed' for j in service.jobs.values())
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    asyncio.run(scenario())


def test_restart_marks_inflight_interrupted(client):
    jid=client.post('/api/songs', json=INPUT, headers=HEADERS).json()['id']
    with TestClient(service.app) as running:
        assert running.get(f'/api/songs/{jid}').json()['status']=='interrupted'


def test_quick_options_validate_and_instrumental_is_explicit(client):
    assert client.post('/api/songs', json={"auto_assist":True}, headers=HEADERS).status_code==202
    assert client.post('/api/songs', json={"choices":{"vocal":"instrumental"}}, headers=HEADERS).status_code==202
    assert client.post('/api/songs', json={"auto_assist":True,"choices":{"bpm":0}}, headers=HEADERS).status_code==422
    preset=client.post('/api/preset', json={"brief":"選択から","choices":{"vocal":"male","genre":"jazz","bpm":92}}, headers=HEADERS).json()
    assert '92 BPM' in preset['style'] and 'male lead vocal' in preset['style']


def test_auto_assist_preserves_lyrics_seed_and_score(client, monkeypatch):
    async def fake(request):
        assert request.current_abc=='X:1\nQ:1/4=90\nK:C\nCDEF|'
        assert request.reference_track=='参考曲名'
        return {"title":"AI title", "style":"Jazz at 90 BPM", "lyrics":"Changed lyrics", "melody_plan":"短いモチーフを展開", "tips":[], "explanation":"説明"}
    monkeypatch.setattr(service.bridge,'compose',fake)
    data={**INPUT,"auto_assist":True,"seed":123,"abc":"X:1\nQ:1/4=90\nK:C\nCDEF|","reference_track":"参考曲名"}
    jid=client.post('/api/songs',json=data,headers=HEADERS).json()['id']
    before=(service.JOBS/jid/'submitted.json').read_text()
    effective=asyncio.run(service.prepare_song(service.JOBS/jid,SongInput(**data)))
    assert effective.lyrics==INPUT['lyrics'] and effective.seed==123 and effective.abc==data['abc']
    assert effective.title=='Test' and not effective.auto_assist
    assert before==(service.JOBS/jid/'submitted.json').read_text()
    assert (service.JOBS/jid/'assistance.json').exists()


def test_instrumental_drops_sung_words_and_reuse_is_stable(client):
    data={**INPUT,'choices':{'vocal':'instrumental'}}
    jid=client.post('/api/songs',json=data,headers=HEADERS).json()['id']
    result=asyncio.run(service.prepare_song(service.JOBS/jid,SongInput(**data)))
    assert result.lyrics=='[Instrumental]'
    again=asyncio.run(service.prepare_song(service.JOBS/jid,result))
    assert again.style==result.style


@pytest.mark.parametrize('cancel_it',[True,False])
def test_preparation_cancel_or_failure_never_launches_gpu(client, monkeypatch, cancel_it):
    async def scenario():
        entered=asyncio.Event()
        async def fake(request):
            entered.set()
            if cancel_it: await asyncio.Future()
            raise RuntimeError('test quota error')
        async def forbidden(*args,**kwargs):
            pytest.fail('GPU must not start after preparation failed/cancelled')
        monkeypatch.setattr(service.bridge,'compose',fake)
        monkeypatch.setattr(service.asyncio,'create_subprocess_exec',forbidden)
        job=await service.create_song(SongInput(auto_assist=True))
        task=asyncio.create_task(service.run_queue())
        try:
            await asyncio.wait_for(entered.wait(),2)
            if cancel_it: await service.cancel(job['id'])
            await asyncio.wait_for(service.queue.join(),2)
            assert service.jobs[job['id']]['status']==('cancelled' if cancel_it else 'failed')
            assert not task.done(), 'queue must continue after a cancelled job'
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
    asyncio.run(scenario())


def test_generated_title_retries_library_duplicate(client, monkeypatch):
    service.jobs['old']={'id':'old','title':'Neon Afterglow','status':'completed','created_at':0}
    calls=[]
    async def fake(request):
        calls.append(request)
        assert 'Neon Afterglow' in request.recent_titles
        assert request.current_abc=='X:1\nK:C\nCDEF|' and request.reference_track=='参考の曲'
        return {'title':'Neon Afterglow' if len(calls)==1 else '切手を貼らずに',
                'style':'Warm jazz pop','lyrics':'[Verse]\nAn original line','tips':[]}
    monkeypatch.setattr(service.bridge,'compose',fake)
    request=SongInput(auto_assist=True,brief='手紙を書きかける曲',abc='X:1\nK:C\nCDEF|',reference_track='参考の曲')
    jid=client.post('/api/songs',json=request.model_dump(),headers=HEADERS).json()['id']
    result=asyncio.run(service.prepare_song(service.JOBS/jid,request))
    assert result.title=='切手を貼らずに' and len(calls)==2


def test_derivative_draft_and_source_snapshot(client, monkeypatch):
    source=client.post('/api/songs',json=INPUT,headers=HEADERS).json()['id']
    service.jobs[source]['status']='completed'
    folder=service.JOBS/source
    (folder/'artifacts').mkdir()
    abc='X:1\nM:4/4\nQ:1/4=104\nK:C\nC4|'
    (folder/'artifacts/score.abc').write_text(abc)
    (folder/'audio.m4a').write_bytes(b'original-audio')
    draft=client.post(f'/api/songs/{source}/derive',json={'mode':'score'},headers=HEADERS)
    assert draft.status_code==200
    request=draft.json()['input']
    assert request['abc']==abc and request['lyrics']==INPUT['lyrics']
    assert request['source_song_id']==source and request['album_title']==''
    request.update(auto_assist=False,abc='user attempt to replace source',lyrics='changed lyrics')
    response=client.post('/api/songs',json=request,headers=HEADERS)
    assert response.status_code==202
    child=service.JOBS/response.json()['id']
    actual=json.loads((child/'input.json').read_text())
    assert actual['abc']==abc and actual['lyrics']==INPUT['lyrics']
    assert json.loads((child/'derivation.json').read_text())['source_song_id']==source
    monkeypatch.setattr(service,'engine_status',lambda root:{'ace-xl-turbo':{'ready':True}})
    cover=client.post(f'/api/songs/{source}/derive',json={'mode':'cover'},headers=HEADERS).json()['input']
    response=client.post('/api/songs',json=cover,headers=HEADERS)
    assert response.status_code==202
    child=service.JOBS/response.json()['id']
    (folder/'audio.m4a').unlink()
    assert (child/'source-audio.m4a').read_bytes()==b'original-audio'


def test_derivative_rejects_missing_source_and_invalid_modes(client):
    source=client.post('/api/songs',json=INPUT,headers=HEADERS).json()['id']
    assert client.post(f'/api/songs/{source}/derive',json={'mode':'score'},headers=HEADERS).status_code==400
    service.jobs[source]['status']='completed'
    assert client.post(f'/api/songs/{source}/derive',json={'mode':'score'},headers=HEADERS).status_code==400
    assert client.post('/api/songs',json={**INPUT,'source_song_id':'../../etc/passwd','derivation_mode':'score'},headers=HEADERS).status_code==422
    assert client.post('/api/songs',json={**INPUT,'source_song_id':'a'*16,'derivation_mode':'score'},headers=HEADERS).status_code==400
    assert client.post('/api/songs',json={**INPUT,'derivation_mode':'cover'},headers=HEADERS).status_code==422


def test_single_auto_duration_is_resolved_before_worker(tmp_path,monkeypatch):
    from unittest.mock import AsyncMock
    from schemas import AssistInput
    compose=AsyncMock(return_value={'title':'Chosen name','style':'Piano with resolved outro','lyrics':'[Instrumental]','duration':137})
    monkeypatch.setattr(service.bridge,'compose',compose)
    request=SongInput(engine='ace-xl-turbo',title='Specific user title',duration_mode='auto',auto_assist=False,choices=MusicChoices(vocal='instrumental'))
    assert request.auto_assist
    resolved=asyncio.run(service.prepare_song(tmp_path,request))
    assert resolved.duration==137 and resolved.duration_mode=='fixed'
    assert not resolved.auto_assist
    assert compose.call_args.args[0].duration_mode=='auto'
    saved=json.loads((tmp_path/'input.json').read_text())
    assert saved['duration']==137
    with pytest.raises(ValueError):SongInput(engine='yue2',duration_mode='auto')


def test_delete_song_guards_and_album_tombstone(client,tmp_path,monkeypatch):
    from types import SimpleNamespace
    jid=client.post('/api/songs',json=INPUT,headers=HEADERS).json()['id']
    path=f'/api/songs/{jid}/delete'
    assert client.post(path,json={'title':'Test'},headers=HEADERS).status_code==409
    service.jobs[jid]['status']='completed'
    assert client.post(path,json={'title':'Wrong'},headers=HEADERS).status_code==409
    root=tmp_path/'albums';(root/'album').mkdir(parents=True)
    (root/'album'/'album.zip').write_text('old export')
    item={'id':'album','song_ids':[jid],'status':'generating'}
    saved=[]
    manager=SimpleNamespace(items={'album':item},export_lock=asyncio.Lock(),root=root,save=lambda a:saved.append(dict(a)))
    from albums import AlbumManager
    manager.invalidate_video=lambda a:AlbumManager.invalidate_video(manager,a)
    monkeypatch.setattr(service,'album_manager',manager)
    assert client.post(path,json={'title':'Test'},headers=HEADERS).status_code==409
    item['status']='completed'
    assert client.post(path,json={'title':'Test'}).status_code==403
    assert client.post(path,json={'title':'Test'},headers=HEADERS).status_code==200
    assert not (service.JOBS/jid).exists() and jid not in service.jobs
    assert item['song_ids']==[None] and item['deleted_tracks']==[0]
    assert not (root/'album'/'album.zip').exists() and saved
    assert client.get(f'/api/songs/{jid}').status_code==404

@pytest.mark.parametrize('explicit,expected',[(None,160),(155,155)])
def test_assist_bpm_reaches_generator_without_overriding_user(tmp_path,monkeypatch,explicit,expected):
    from unittest.mock import AsyncMock
    compose=AsyncMock(return_value={'title':'User name','style':'Driving Eurobeat','lyrics':'[Instrumental]','duration':180,'bpm':160})
    monkeypatch.setattr(service.bridge,'compose',compose)
    request=SongInput(engine='ace-xl-turbo',title='User name',auto_assist=True,choices=MusicChoices(vocal='instrumental',bpm=explicit))
    resolved=asyncio.run(service.prepare_song(tmp_path,request))
    assert resolved.choices.bpm==expected
    assert json.loads((tmp_path/'input.json').read_text())['choices']['bpm']==expected


def test_yue_instrumental_break_is_preserved_in_vocal_song(tmp_path,monkeypatch):
    from unittest.mock import AsyncMock
    lyrics='[Verse]\nA brand new road\n\n[Instrumental]\n\n[Chorus]\nWe carry on'
    compose=AsyncMock(return_value={'title':'Road','style':'Pop with a guitar-led instrumental break','lyrics':'changed words'})
    monkeypatch.setattr(service.bridge,'compose',compose)
    request=SongInput(engine='yue2',title='Road',style='Pop',lyrics=lyrics,auto_assist=True,choices=MusicChoices(vocal='male'))
    result=asyncio.run(service.prepare_song(tmp_path,request))
    assert result.lyrics==lyrics
    assert compose.call_args.args[0].current_lyrics==lyrics
    assert compose.call_args.args[0].preserve_lyrics
    assert json.loads((tmp_path/'input.json').read_text())['lyrics']==lyrics
