"""Google OAuth and resumable uploads. Credentials are never exposed in album JSON."""
import asyncio
import json
import os
import secrets
import time
from urllib.parse import urlencode, urlparse
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

REDIRECT='http://localhost:7860/api/youtube/callback'
SCOPE='https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly'

class PublishInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title: str=Field(min_length=1,max_length=100,pattern=r'^[^<>\x00-\x1f]+$')
    description: str=Field(max_length=5000,pattern=r'^[^<>\x00-\x08\x0b\x0c\x0e-\x1f]*$')
    privacy: Literal['private','unlisted','public']='private'
    made_for_kids: bool
    contains_synthetic_media: bool=True
    confirmed: Literal[True]


def install_youtube(app, manager_getter, private_dir):
    private_dir.mkdir(parents=True,exist_ok=True);private_dir.chmod(0o700)
    router=APIRouter(prefix='/api/youtube')
    pending={};tasks={}
    def path(name):return private_dir/name
    def read(name):return json.loads(path(name).read_text()) if path(name).exists() else {}
    def save(name,data):
        tmp=path(name+'.tmp')
        fd=os.open(tmp,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as f:json.dump(data,f)
        tmp.replace(path(name))
    def local(request):
        if request.url.hostname not in ('localhost','127.0.0.1','::1') or not request.client or request.client.host not in ('127.0.0.1','::1','testclient'):
            raise HTTPException(403,'YouTubeへの接続・投稿は、このPCの http://localhost:7860 で操作してください')
    def owner(request):
        local(request)
        stored=read('tokens.json')
        if not stored.get('owner') or not secrets.compare_digest(request.cookies.get('otoni_youtube',''),stored['owner']):
            raise HTTPException(401,'このブラウザでYouTubeに接続してください')
    async def access(client):
        tokens=read('tokens.json');config=read('client.json')
        if not tokens.get('refresh_token'):raise RuntimeError('YouTubeに接続し直してください')
        r=await client.post('https://oauth2.googleapis.com/token',data={**config,'refresh_token':tokens['refresh_token'],'grant_type':'refresh_token'})
        if r.status_code!=200:raise RuntimeError('Googleの認証が失効しました。接続し直してください')
        return r.json()['access_token']
    @router.get('/status')
    async def status(request:Request):
        tokens=read('tokens.json')
        return {'configured':bool(read('client.json')),'connected':bool(tokens.get('refresh_token')),
                'channel':tokens.get('channel',''),'authorized_browser':bool(tokens.get('owner')) and secrets.compare_digest(request.cookies.get('otoni_youtube',''),tokens.get('owner','')),
                'redirect_uri':REDIRECT}
    @router.post('/configure')
    async def configure(request:Request):
        local(request)
        body=await request.json();web=body.get('web',{})
        if not isinstance(web,dict) or not isinstance(web.get('client_id'),str) or not web['client_id'].endswith('.apps.googleusercontent.com') or not isinstance(web.get('client_secret'),str) or not web['client_secret'] or REDIRECT not in web.get('redirect_uris',[]):
            raise HTTPException(400,'ウェブアプリ用OAuth JSONと、指定のリダイレクトURIが必要です')
        if any(not t.done() for t in tasks.values()):raise HTTPException(409,'投稿が完了するまで設定を変更できません')
        save('client.json',{k:web[k] for k in ('client_id','client_secret')})
        path('tokens.json').unlink(missing_ok=True)
        return {'configured':True}
    @router.post('/connect')
    async def connect(request:Request):
        local(request)
        if request.url.hostname!='localhost':
            raise HTTPException(409,'Googleへの接続は http://localhost:7860 で行ってください')
        config=read('client.json')
        if not config:raise HTTPException(409,'最初にGoogle OAuth設定を読み込んでください')
        if any(not t.done() for t in tasks.values()):raise HTTPException(409,'投稿の完了をお待ちください')
        now=time.time()
        for key in list(pending):
            if pending[key]<now:pending.pop(key)
        state=secrets.token_urlsafe(32);pending[state]=now+600
        from fastapi.responses import JSONResponse
        response=JSONResponse({'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':config['client_id'],'redirect_uri':REDIRECT,'response_type':'code','scope':SCOPE,'access_type':'offline','prompt':'consent','state':state})})
        response.set_cookie('otoni_oauth_state',state,httponly=True,samesite='lax',max_age=600)
        return response
    @router.get('/callback')
    async def callback(request:Request,state:str='',code:str=''):
        local(request)
        valid=pending.pop(state,0)
        if valid<time.time() or not secrets.compare_digest(state,request.cookies.get('otoni_oauth_state','')):
            raise HTTPException(400,'接続確認が失効しました。もう一度接続してください')
        if not code:raise HTTPException(400,'Googleへの接続がキャンセルされました')
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.post('https://oauth2.googleapis.com/token',data={**read('client.json'),'code':code,'redirect_uri':REDIRECT,'grant_type':'authorization_code'})
            if r.status_code!=200:raise HTTPException(400,'Googleへの接続に失敗しました')
            tokens=r.json()
            if not tokens.get('refresh_token'):raise HTTPException(400,'継続接続の許可が得られませんでした。接続し直してください')
            ch=await client.get('https://www.googleapis.com/youtube/v3/channels',params={'part':'snippet','mine':'true'},headers={'Authorization':'Bearer '+tokens['access_token']})
            if ch.status_code!=200 or not ch.json().get('items'):raise HTTPException(400,'投稿先のYouTubeチャンネルを確認できません')
            channel=ch.json()['items'][0]
        key=secrets.token_urlsafe(32)
        save('tokens.json',{'refresh_token':tokens['refresh_token'],'channel':channel['snippet']['title'],'channel_id':channel['id'],'owner':key})
        response=RedirectResponse('/#albums',status_code=303)
        response.delete_cookie('otoni_oauth_state')
        response.set_cookie('otoni_youtube',key,httponly=True,samesite='strict',max_age=86400*30)
        return response
    @router.post('/disconnect')
    async def disconnect(request:Request):
        owner(request)
        if any(not t.done() for t in tasks.values()):raise HTTPException(409,'投稿の完了をお待ちください')
        token=read('tokens.json').get('refresh_token')
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.post('https://oauth2.googleapis.com/revoke',data={'token':token})
            if r.status_code not in (200,400):raise HTTPException(502,'Googleとの接続解除に失敗しました。再試行してください')
        path('tokens.json').unlink(missing_ok=True)
        return {'connected':False}
    async def upload(aid,options):
        manager=manager_getter();item=manager.get(aid);session_name=aid+'-upload.json'
        try:
            video=manager.root/aid/'youtube.mp4';size=video.stat().st_size
            async with httpx.AsyncClient(timeout=120,follow_redirects=False) as client:
                headers={'Authorization':'Bearer '+await access(client)}
                session=read(session_name)
                if session and session.get('channel_id')!=read('tokens.json')['channel_id']:
                    raise RuntimeError('投稿を開始したチャンネルに接続し直してください')
                if not session:
                    body={'snippet':{'title':options['title'],'description':options['description'],'categoryId':'10'},'status':{'privacyStatus':options['privacy'],'selfDeclaredMadeForKids':options['made_for_kids'],'containsSyntheticMedia':options['contains_synthetic_media']}}
                    r=await client.post('https://www.googleapis.com/upload/youtube/v3/videos',params={'uploadType':'resumable','part':'snippet,status'},headers={**headers,'X-Upload-Content-Length':str(size),'X-Upload-Content-Type':'video/mp4'},json=body)
                    if r.status_code not in (200,201):raise RuntimeError(f'YouTubeが投稿開始を受け付けませんでした（HTTP {r.status_code}）。APIの有効化と割り当てを確認してください')
                    url=r.headers.get('location','');parsed=urlparse(url)
                    if parsed.scheme!='https' or parsed.hostname not in ('www.googleapis.com','youtube.googleapis.com'):raise RuntimeError('アップロード先を検証できません')
                    session={'url':url,'channel_id':read('tokens.json')['channel_id']};save(session_name,session)
                r=await client.put(session['url'],headers={**headers,'Content-Range':f'bytes */{size}'},content=b'')
                with video.open('rb') as f:
                    while r.status_code==308:
                        end=r.headers.get('range','')
                        offset=int(end.rsplit('-',1)[1])+1 if end else 0
                        if offset>=size:raise RuntimeError('YouTubeの完了状態を確認できません。再開してください')
                        f.seek(offset);chunk=f.read(8*1024*1024)
                        r=await client.put(session['url'],headers={**headers,'Content-Type':'video/mp4','Content-Range':f'bytes {offset}-{offset+len(chunk)-1}/{size}'},content=chunk)
                        item['youtube']['progress']=min(99,round((offset+len(chunk))/size*100));manager.save(item)
                if r.status_code not in (200,201):raise RuntimeError(f'送信が停止しました（HTTP {r.status_code}）。再開して状態を確認できます')
                result=r.json()
                if not result.get('id'):raise RuntimeError('投稿結果を確認できません。再開してください')
                item['youtube'].update(status='completed',video_id=result['id'],privacy=result.get('status',{}).get('privacyStatus','unknown'),progress=100)
                path(session_name).unlink(missing_ok=True)
        except asyncio.CancelledError:
            item['youtube']['status']='interrupted';raise
        except Exception as exc:
            # Do not expose httpx URLs, which may contain resumable session tokens.
            item['youtube'].update(status='failed',error='通信が中断されました。再開できます' if isinstance(exc,httpx.HTTPError) else str(exc))
        finally:manager.save(item)
    @router.post('/albums/{aid}/publish',status_code=202)
    async def publish(aid:str,options:PublishInput,request:Request):
        owner(request)
        manager=manager_getter();item=manager.get(aid)
        if item.get('video_status')!='completed':raise HTTPException(409,'動画の書き出しを先に完了してください')
        previous=item.get('youtube',{})
        if previous.get('status')=='completed':raise HTTPException(409,'このアルバムは投稿済みです。YouTube Studioで管理できます')
        if any(not t.done() for t in tasks.values()):raise HTTPException(409,'別の投稿処理が進行中です')
        data=options.model_dump()
        if previous.get('options') and previous['options']!=data:raise HTTPException(409,'中断した投稿は最初に確認した内容で再開してください')
        item['youtube']={'status':'uploading','options':data,'channel':read('tokens.json')['channel'],'progress':0};manager.save(item)
        tasks[aid]=asyncio.create_task(upload(aid,data))
        return item['youtube']
    app.include_router(router)
    async def close():
        for task in tasks.values():task.cancel()
        await asyncio.gather(*tasks.values(),return_exceptions=True)
    return close
