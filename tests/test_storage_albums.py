import asyncio
import json
import subprocess
import wave
import math
import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from audio_storage import finalize_audio, stored_audio
from album_schemas import AlbumInput, AlbumPlan
from albums import AlbumManager
from title_variety import similar_title


def wav(folder):
    folder.mkdir(parents=True,exist_ok=True)
    with wave.open(str(folder/'song.wav'),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(48000)
        f.writeframes(b''.join(struct.pack('<hh',int(8000*math.sin(i*.05)),int(8000*math.sin(i*.06))) for i in range(48000)))


def test_m4a_verified_before_original_removal(tmp_path):
    wav(tmp_path)
    result=finalize_audio(tmp_path,'m4a','Test','Album',1)
    assert result['bytes']>1000 and result['saved_bytes']>0
    assert not (tmp_path/'song.wav').exists()
    assert stored_audio(tmp_path)=='audio.m4a'
    assert abs(result['audio_seconds']-1)<.1
    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(tmp_path/'audio.m4a')]))
    assert metadata['format']['tags']['album']=='Album'


def test_failed_conversion_preserves_wav(tmp_path,monkeypatch):
    wav(tmp_path)
    def fail(*args,**kwargs): raise subprocess.CalledProcessError(1,args[0])
    monkeypatch.setattr(subprocess,'run',fail)
    with pytest.raises(subprocess.CalledProcessError): finalize_audio(tmp_path)
    assert (tmp_path/'song.wav').is_file() and not (tmp_path/'audio.m4a').exists()


def test_flac_storage_and_duplicate_audio_cleanup(tmp_path):
    wav(tmp_path)
    (tmp_path/'ace-output').mkdir();(tmp_path/'ace-output/duplicate.wav').write_bytes(b'duplicate')
    (tmp_path/'artifacts').mkdir();(tmp_path/'artifacts/score.abc').write_text('X:1')
    result=finalize_audio(tmp_path,'flac')
    assert result['format']=='flac' and not list(tmp_path.rglob('*.wav'))
    assert (tmp_path/'artifacts/score.abc').read_text()=='X:1'


def test_title_similarity_and_album_validation():
    assert similar_title('ＮＥＯＮ Ride',['Neon Ride'])
    assert similar_title('Neon Rides',['Neon Ride'])
    assert not similar_title('切手を貼らずに',['ダイヤルを戻して'])
    with pytest.raises(ValueError): AlbumInput(brief='test album',track_count=30)
    t={'title':'Same','brief':'original track','role':'opening','bpm':100,'vocal':'male','genre':'citypop'}
    with pytest.raises(ValueError): AlbumPlan(title='Album',concept='a new coherent concept',cover_prompt='An original square image of a music album',tracks=[t,t])


def test_album_resume_keeps_completed_track_and_export(tmp_path):
    async def scenario():
        data=tmp_path/'songs';data.mkdir()
        for jid in ['done','retry']:
            folder=data/jid;wav(folder);finalize_audio(folder)
            (folder/'input.json').write_text(json.dumps({'style':'jazz','lyrics':'words'}))
        jobs={'done':{'id':'done','title':'First','status':'completed'},'retry':{'id':'retry','title':'Second','status':'failed'}}
        queue=asyncio.Queue()
        service=SimpleNamespace(JOBS=data,jobs=jobs,IN_FLIGHT=('queued','running','preparing'),queue=queue,
            save_job=lambda j:None,public_job=lambda j:dict(j),bridge=None)
        manager=AlbumManager(service)
        track=lambda title:{'title':title,'role':'role','brief':'new detailed brief','bpm':100,'vocal':'male','genre':'citypop'}
        item={'id':'abc','status':'failed','title':'Album','request':AlbumInput(brief='test concept',track_count=2,generate_cover=False).model_dump(),
              'song_ids':['done','retry'],'created_at':0,'plan':{'title':'Album','concept':'A coherent new concept','cover_prompt':'original square jacket art direction','tracks':[track('First'),track('Second')]}}
        manager.items['abc']=item;manager.save(item)
        async def finish():
            jid=await queue.get();assert jid=='retry';jobs[jid]['status']='completed'
        fin=asyncio.create_task(finish())
        await manager.run('abc');await fin
        assert item['song_ids']==['done','retry'] and item['status']=='completed'
        path=manager.export('abc')
        import zipfile
        with zipfile.ZipFile(path) as z:
            assert len([n for n in z.namelist() if n.endswith('.m4a')])==2
        await manager.close()
    asyncio.run(scenario())


def test_public_album_with_unstarted_tracks(tmp_path):
    service=SimpleNamespace(JOBS=tmp_path/'songs',jobs={},public_job=lambda j:j)
    manager=AlbumManager(service)
    result=manager.public({'id':'test','song_ids':[None,None],'status':'generating'})
    assert result['completed']==0 and result['songs']==[None,None]


def test_album_pause_cancels_cover_and_only_active_songs(tmp_path):
    async def scenario():
        jobs={'done':{'status':'completed'},'active':{'status':'running'}}
        cancel=AsyncMock()
        service=SimpleNamespace(JOBS=tmp_path/'songs',jobs=jobs,IN_FLIGHT=('running','queued','preparing'),cancel=cancel,public_job=lambda j:j)
        manager=AlbumManager(service)
        item={'id':'one','status':'generating','song_ids':['done','active'],'cover_status':'generating'}
        manager.items['one']=item;manager.save(item)
        manager.tasks['one']=asyncio.create_task(asyncio.sleep(100))
        manager.cover_tasks['one']=asyncio.create_task(asyncio.sleep(100))
        await manager.pause('one')
        cancel.assert_awaited_once_with('active')
        assert manager.cover_tasks['one'].cancelled() and item['status']=='paused'
        await manager.close()
    asyncio.run(scenario())


def test_codex_empty_lyrics_request_does_not_preserve_blank(monkeypatch):
    from codex_bridge import CodexBridge
    from schemas import AssistInput
    async def scenario():
        bridge=CodexBridge()
        captured=[]
        async def rpc(method, params=None):
            if method=='account/read': return {'account':{'type':'chatgpt'}}
            if method=='thread/start': return {'thread':{'id':'t'}}
            if method=='turn/start':
                payload=json.loads(params['input'][0]['text']);captured.append(payload)
                draft={'title':'New Song','style':'Soulful house with female vocals','lyrics':'[Verse]\nAn original verse',
                       'explanation':'説明','tips':[],'melody_plan':'方針','reference_analysis':'','originality_note':'新規'}
                q=bridge.queues['t'];q.put_nowait({'method':'item/completed','params':{'item':{'type':'agentMessage','text':json.dumps(draft)}}})
                q.put_nowait({'method':'turn/completed','params':{'turn':{'status':'completed'}}})
                return {'turn':{'id':'turn'}}
            return {}
        monkeypatch.setattr(bridge,'rpc',rpc)
        result=await bridge.compose(AssistInput(engine='ace-xl-turbo',brief='新しい歌を作る',current_lyrics='',preserve_lyrics=True))
        assert captured[0]['preserve_lyrics'] is False and result['lyrics'].startswith('[Verse]')
    asyncio.run(scenario())


def test_album_new_tracks_keep_user_sound_without_coarse_genre_override(tmp_path):
    async def scenario():
        jobs = {}
        received = []
        async def create_song(song):
            received.append(song)
            jid = str(len(received))
            jobs[jid] = {'id': jid, 'status': 'completed'}
            return jobs[jid]
        service = SimpleNamespace(JOBS=tmp_path/'songs', jobs=jobs, bridge=None,
            IN_FLIGHT=('queued','running'), create_song=create_song, save_job=lambda j: None)
        manager = AlbumManager(service)
        original = 'R4のような90年代末のジャズハウス。現代的EDMにはしない。'
        tracks = [{'title': name, 'role':'race', 'brief':'jazzy house with syncopated bass',
            'bpm':120, 'vocal':'instrumental', 'genre':'edm'} for name in ['First Turn','Second Lap']]
        item = {'id':'sound', 'status':'planning', 'song_ids':[None,None],
            'request':AlbumInput(brief=original,track_count=2,generate_cover=False).model_dump(),
            'plan':{'title':'Race', 'concept':'An automatically invented game world',
                'cover_prompt':'Original square album illustration for racing', 'tracks':tracks}}
        manager.items['sound'] = item
        await manager.run('sound')
        assert item['status'] == 'completed'
        assert len(received) == 2
        for song in received:
            assert original in song.brief
            assert 'jazzy house with syncopated bass' in song.brief
            assert song.choices.genre == 'auto'
            assert song.choices.melody == 'balanced'
            assert song.choices.bpm == 120
        await manager.close()
    asyncio.run(scenario())

@pytest.mark.parametrize('mode,expected', [('auto',[95,167]),('fixed',[120,120])])
def test_album_track_duration_reaches_song_input(tmp_path,mode,expected):
    async def scenario():
        jobs,received={},[]
        async def create_song(song):
            received.append(song)
            jid=str(len(received));jobs[jid]={'id':jid,'status':'completed'}
            return jobs[jid]
        service=SimpleNamespace(JOBS=tmp_path/'songs',jobs=jobs,bridge=None,IN_FLIGHT=('queued','running'),create_song=create_song,save_job=lambda j:None)
        manager=AlbumManager(service)
        tracks=[dict(title=name,role='drive',brief='jazzy electric piano',bpm=110,vocal='instrumental',genre='jazz',duration=seconds,ending='ピアノ主題を回収して解決する') for name,seconds in [('First Turn',95),('Second Lap',167)]]
        item=dict(id='durationtest',status='generating',title='Test Album',request=AlbumInput(brief='夜のドライブ',engine='ace-xl-turbo',duration_mode=mode,duration=120,track_count=2,generate_cover=False).model_dump(),song_ids=[None,None],plan=dict(title='Test Album',concept='A coherent driving album',cover_prompt='original abstract landscape album cover',tracks=tracks))
        manager.items[item['id']]=item
        await manager.run(item['id'])
        assert item['status']=='completed'
        assert [s.duration for s in received]==expected
        assert all('ピアノ主題を回収して解決する' in s.brief for s in received)
        await manager.close()
    asyncio.run(scenario())


def test_album_research_cached_across_planning_failure(tmp_path,monkeypatch):
    import albums
    async def scenario():
        research={'mode':'knowledge','musical_features':'Eurobeat'}
        bridge=SimpleNamespace(assist_lock=asyncio.Lock(),research_reference=AsyncMock(return_value=research))
        service=SimpleNamespace(JOBS=tmp_path/'songs',jobs={},bridge=bridge)
        manager=AlbumManager(service)
        request=AlbumInput(brief='Fast Eurobeat album',engine='ace-xl-turbo',duration_mode='auto',generate_cover=False)
        item={'id':'test','title':'Pending','request':request.model_dump(),'song_ids':[],'status':'planning'}
        manager.items['test']=item
        planner=AsyncMock(side_effect=RuntimeError('temporary planning failure'))
        monkeypatch.setattr(albums,'run_task',planner)
        await manager.run('test')
        await manager.run('test')
        bridge.research_reference.assert_awaited_once()
        assert planner.await_count==2
        payload=planner.call_args.args[2]
        assert payload['duration'] is None and payload['reference_research']==research
        assert json.loads((manager.root/'test'/'album.json').read_text())['reference_research']==research
    asyncio.run(scenario())
