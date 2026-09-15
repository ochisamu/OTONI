import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from albums import AlbumManager
from album_schemas import AlbumRename
from test_storage_albums import wav


def manager(tmp_path):
    songs=tmp_path/'songs';wav(songs/'one');wav(songs/'two')
    for jid in ('one','two'):(songs/jid/'input.json').write_text(json.dumps({'album_title':'Old'}))
    jobs={jid:{'id':jid,'title':jid,'status':'completed'} for jid in ('one','two')}
    m=AlbumManager(SimpleNamespace(JOBS=songs,jobs=jobs,save_job=lambda j:None,public_job=lambda j:j))
    item={'id':'album','title':'Old','status':'completed','song_ids':['one','two'],'request':{'engine':'yue2'},'plan':{'title':'Old','cover_prompt':'Cover with Old title','concept':'An original album'},'cover_status':'completed','cover_file':'cover.png'}
    m.items['album']=item;m.save(item)
    from PIL import Image
    Image.new('RGB',(64,64),'navy').save(m.root/'album'/'cover.png')
    return m,item


def test_rename_updates_album_and_input_and_invalidates_video(tmp_path):
    m,item=manager(tmp_path)
    (m.root/'album'/'youtube.mp4').write_bytes(b'old')
    item['video_status']='completed'
    result=m.rename('album','New')
    assert result['title']=='New' and item['plan']['title']=='New'
    assert 'New' in item['plan']['cover_prompt']
    assert json.loads((m.s.JOBS/'one'/'input.json').read_text())['album_title']=='New'
    assert 'video_status' not in item and not (m.root/'album'/'youtube.mp4').exists()
    item['video_status']='generating'
    with pytest.raises(HTTPException):m.rename('album','Other')
    for title in ('   ','bad\nname'):
        with pytest.raises(ValueError):AlbumRename(title=title)


def test_cover_failure_preserves_previous_and_success_refreshes_cache(tmp_path,monkeypatch):
    import albums
    async def scenario():
        m,item=manager(tmp_path);old=(m.root/'album'/'cover.png').read_bytes()
        monkeypatch.setattr(albums,'generate_cover',AsyncMock(side_effect=RuntimeError('failure')))
        await m.cover('album')
        assert (m.root/'album'/'cover.png').read_bytes()==old and item['cover_status']=='failed'
        fake=AsyncMock(return_value='cover.png');monkeypatch.setattr(albums,'generate_cover',fake)
        item['cover_direction']='Blue flowers'
        await m.cover('album')
        assert item['cover_revision']==1 and '?v=1' in m.public(item)['cover_url']
        assert 'Blue flowers' in fake.call_args.args[2]
    asyncio.run(scenario())


@pytest.mark.parametrize("deleted", [True, False])
def test_real_video_duration_and_deleted_track_exclusion(tmp_path,deleted):
    async def scenario():
        m,item=manager(tmp_path)
        if deleted:item['deleted_tracks']=[1];item['song_ids'][1]=None
        m.start_video('album');await m.video_tasks['album']
        assert item['video_status']=='completed',item.get('video_error')
        assert abs(item['video_seconds']-(1 if deleted else 2))<.15
        text=(m.root/'album'/'youtube-description.txt').read_text()
        assert '00:00 one' in text
        assert ('00:01 two' in text) is (not deleted)
        import subprocess
        streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(m.root/'album'/'youtube.mp4')]))['streams']
        assert {s['codec_name'] for s in streams}=={'h264','aac'}
        assert not list((m.root/'album').glob('video-*'))
    asyncio.run(scenario())


def test_video_title_cards_switch_with_audio(tmp_path):
    import subprocess
    from io import BytesIO
    from PIL import Image, ImageChops, ImageStat
    from video_artwork import title_card, fit_lines
    async def scenario():
        m,item=manager(tmp_path)
        m.s.jobs['one']['title']='夜の余白 / Stay a Little Longer'
        m.s.jobs['two']['title']='Second: 100% [Original]'
        m.start_video('album');await m.video_tasks['album']
        assert item['video_status']=='completed',item.get('video_error')
        expected=[]
        for i,jid in enumerate(['one','two']):
            card=tmp_path/f'{i}.png'
            title_card(m.root/'album'/'cover.png',item['title'],m.s.jobs[jid]['title'],i+1,2,card)
            expected.append(Image.open(card).convert('RGB').crop((640,260,1220,550)))
        for seconds,match in [(0.5,0),(1.5,1)]:
            raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(seconds),'-i',str(m.root/'album'/'youtube.mp4'),'-frames:v','1','-f','image2pipe','-vcodec','png','-threads','1','-'])
            frame=Image.open(BytesIO(raw)).convert('RGB').crop((640,260,1220,550))
            distance=lambda target:sum(ImageStat.Stat(ImageChops.difference(frame,target)).mean)
            assert distance(expected[match]) < 6
            assert distance(expected[match]) < distance(expected[1-match])
        lines,font=fit_lines('あ'*120,550,5,46,22)
        assert ''.join(lines)=='あ'*120 and len(lines)*font.size*1.3<=250
    asyncio.run(scenario())
