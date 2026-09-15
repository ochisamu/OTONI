import asyncio
from types import SimpleNamespace
import pytest
from albums import AlbumManager
from album_schemas import AlbumInput,AlbumPlan

ENGINES=['yue2','ace-xl-turbo','stable-audio-3-medium']
def plan():
    return AlbumPlan(title='Test album',concept='A coherent collection of original music',cover_prompt='Original square artwork with an abstract composition',tracks=[
        dict(title=title,role='role',brief='Original music with a clear theme',bpm=104,vocal='male' if i==0 else 'instrumental',genre='citypop',engine=engine,engine_reason='Selected for its interface',duration=60+i*10)
        for i,(engine,title) in enumerate(zip(ENGINES,['Paper sail','Blue pencil','Green cup']))])


def test_mixed_validation_and_legacy_default(tmp_path):
    m=AlbumManager(SimpleNamespace(JOBS=tmp_path/'songs'))
    request=AlbumInput(brief='A city pop album',engine='mixed')
    item={'available_engines':ENGINES}
    p=plan();m.resolve_track_engines(item,request,p)
    p.tracks[0].engine='stable-audio-3-medium'
    with pytest.raises(ValueError,match='インスト'):m.resolve_track_engines(item,request,p)
    p=plan()
    with pytest.raises(ValueError,match='利用可能'):m.resolve_track_engines({'available_engines':['yue2']},request,p)
    for t in p.tracks:t.engine='yue2'
    with pytest.raises(ValueError,match='2種類'):m.resolve_track_engines(item,request,p)
    p=plan();m.resolve_track_engines({},AlbumInput(brief='A normal album',engine='ace-xl-turbo'),p)
    assert {t.engine for t in p.tracks}=={'ace-xl-turbo'}


def test_mixed_queue_routes_each_track_and_resume_skips_completed(tmp_path):
    async def scenario():
        songs={};submitted=[]
        async def create_song(request):
            submitted.append(request)
            jid=str(len(submitted));songs[jid]={'id':jid,'title':request.title,'engine':request.engine,'status':'completed'}
            return songs[jid]
        service=SimpleNamespace(JOBS=tmp_path/'songs',jobs=songs,create_song=create_song,save_job=lambda j:None,IN_FLIGHT=('queued','running','preparing'))
        m=AlbumManager(service)
        request=AlbumInput(brief='Mixed city pop album',engine='mixed',track_count=3,generate_cover=False,duration_mode='auto',language='日本語＋英語フレーズ')
        item={'id':'test','title':'Test album','status':'generating','request':request.model_dump(),'available_engines':ENGINES,'plan':plan().model_dump(),'song_ids':[None]*3}
        m.items['test']=item
        await m.run('test')
        assert item['status']=='completed',item.get('error')
        assert [s.engine for s in submitted]==ENGINES
        assert [s.duration for s in submitted]==[60,70,80]
        assert all(s.auto_assist for s in submitted)
        assert all(s.language == "日本語＋英語フレーズ" for s in submitted)
        assert submitted[2].choices.vocal=='instrumental'
        await m.run('test')
        assert len(submitted)==3
    asyncio.run(scenario())
