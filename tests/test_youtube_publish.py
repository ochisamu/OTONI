import asyncio
import json
from types import SimpleNamespace
from urllib.parse import parse_qs,urlparse
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from youtube_publish import install_youtube, REDIRECT


@pytest.mark.parametrize("uncertain_completion", [False, True])
def test_oauth_owner_confirmation_and_resumable_upload(tmp_path,monkeypatch,uncertain_completion):
    import youtube_publish
    calls=[]
    uploaded=False
    def google(req):
        nonlocal uploaded
        calls.append(req)
        if req.url.path=='/token':return httpx.Response(200,json={'access_token':'access','refresh_token':'refresh'})
        if req.url.path.endswith('/channels'):return httpx.Response(200,json={'items':[{'id':'channel','snippet':{'title':'My channel'}}]})
        if req.method=='POST' and req.url.path.endswith('/videos'):
            return httpx.Response(200,headers={'location':'https://www.googleapis.com/upload/session'})
        if req.url.path=='/upload/session':
            if req.headers['content-range'].startswith('bytes */') and not uploaded:return httpx.Response(308)
            if not req.headers['content-range'].startswith('bytes */'):
                uploaded=True
                if uncertain_completion:raise httpx.ReadTimeout('timeout with sensitive session URL')
            return httpx.Response(200,json={'id':'video123','status':{'privacyStatus':'private'}})
        raise AssertionError(str(req.url))
    real=httpx.AsyncClient
    monkeypatch.setattr(youtube_publish.httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(google),**kwargs))
    root=tmp_path/'albums';(root/'a').mkdir(parents=True);(root/'a'/'youtube.mp4').write_bytes(b'video')
    item={'video_status':'completed'}
    manager=SimpleNamespace(root=root,get=lambda aid:item,save=lambda item:None)
    app=FastAPI();close=install_youtube(app,lambda:manager,tmp_path/'private')
    with TestClient(app,base_url='http://localhost:7860') as c:
        config={'web':{'client_id':'test.apps.googleusercontent.com','client_secret':'secret','redirect_uris':[REDIRECT]}}
        assert c.post('/api/youtube/configure',json=config).status_code==200
        assert (tmp_path/'private'/'client.json').stat().st_mode&0o777==0o600
        url=c.post('/api/youtube/connect').json()['url'];state=parse_qs(urlparse(url).query)['state'][0]
        assert c.get('/api/youtube/callback?state=wrong&code=x').status_code==400
        assert c.get('/api/youtube/callback',params={'state':state,'code':'code'},follow_redirects=False).status_code==303
        assert c.get('/api/youtube/callback',params={'state':state,'code':'code'}).status_code==400
        assert 'refresh' not in c.get('/api/youtube/status').text
        options={'title':'Album','description':'Tracks','privacy':'public','made_for_kids':False,'confirmed':True}
        bad={**options,'confirmed':False}
        assert c.post('/api/youtube/albums/a/publish',json=bad).status_code==422
        assert c.post('/api/youtube/albums/a/publish',json=options).status_code==202
        # Await background upload on the TestClient's event loop.
        async def finished():
            for _ in range(100):
                if item.get('youtube',{}).get('status')!='uploading':return
                await asyncio.sleep(.01)
        c.portal.call(finished)
        if uncertain_completion:
            assert item['youtube']['status']=='failed'
            assert 'sensitive' not in item['youtube']['error']
            assert c.post('/api/youtube/albums/a/publish',json=options).status_code==202
            c.portal.call(finished)
        assert item['youtube']['status']=='completed',item
        assert item['youtube']['privacy']=='private' # actual result, not requested public
        assert c.post('/api/youtube/albums/a/publish',json=options).status_code==409
        assert len([r for r in calls if r.method=='POST' and r.url.path.endswith('/videos')])==1
        assert not list((tmp_path/'private').glob('*-upload.json'))
        c.cookies.clear()
        assert c.post('/api/youtube/albums/a/publish',json=options).status_code==401
        c.portal.call(close)


def test_lan_cannot_configure_google_credentials(tmp_path):
    app=FastAPI();install_youtube(app,lambda:None,tmp_path)
    with TestClient(app,base_url='http://192.168.1.5:7860') as c:
        assert c.post('/api/youtube/configure',json={}).status_code==403
