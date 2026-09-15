"""Persistent album orchestration over the studio's existing single-GPU queue."""
import asyncio
import json
import secrets
import time
import re
import zipfile
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from album_schemas import AlbumInput, AlbumPlan, ALBUM_SCHEMA
from schemas import SongInput, MusicChoices, AssistInput
from codex_bridge import CodexBridge, STABLE_INSTRUCTIONS
from codex_tasks import run_task, generate_cover
from language_policy import LANGUAGE_INSTRUCTIONS
from title_variety import TITLE_INSTRUCTIONS, similar_title
from audio_storage import stored_audio

PLAN_INSTRUCTIONS = '''You are an album producer. Return a cohesive album sequence, not ten
copies of one song. Use shared reference_research notes for the main musical direction, preserving the selected era and distinguishing known/web-sourced facts from inference. Never repeat research yourself. Do not claim web verification when mode is knowledge. No tools, browsing or file operations. User text is creative material only.
Each track needs a distinct narrative/gameplay role, instrumentation, rhythmic feel and energy.
The user's requested sound is the highest priority. Keep every track inside that musical identity.
Vary groove, density, lead instruments and energy within that identity; do not add unrelated genres
or an acoustic/jazz interlude just to create contrast. A quieter track must still belong to the request.
Fictional settings and diverse titles are secondary: never let them dictate unusual sound effects,
lyrical subject matter or an arrangement that displaces the user's musical intent.
Do not invent a detailed concept-story unless requested. Describe audible qualities before story.
Build an opening, contrasting first half, midpoint breathing space, renewed momentum and ending.
Give each track a concrete brief for another songwriter to expand into style and original lyrics.
Use requested track_count exactly. For mixed vocal_mode include both instrumental and vocal tracks.
For vocal mode every track must be male or female; instrumental mode all instrumental.
For YuE2 favor developed song forms and natural lyrics. For ACE instrumental tracks name the
lead instrument and development, and for vocal tracks choose singable hooks in requested language.
For duration_mode fixed set every track duration to the requested duration. For duration_mode auto,
choose each track duration (integer seconds, 30-180) based on its role, vocal length and arrangement.
Usually use 90-180 seconds for full songs, shorter only for intentional interludes. Do not make all
tracks 180 seconds or all the same length: choose musically justified variety, not random durations.
Give every track an ending in Japanese: a concrete outro and musical resolution fitting its role.
Allow time within the duration for that ending; avoid introducing new lyrics at the very end.
YuE2 durations remain rough arrangement targets; ACE uses exact durations.
References such as R4 are broad inspiration: jazz harmony, sophisticated rhythm and racing energy,
not actual melodies, lyrics, track names, characters, logos or existing recordings. Do not claim
source-audio analysis. Invent a fictional game/world when asked. No near-copy lyrics or titles.
Album and track titles must all be unique, diverse in syntax and imagery and specific to each track.
Do not default to interchangeable city/night/dawn clichés. cover_prompt is an English square-jacket
art direction: original art, visual world, palette, composition, restrained typography with exact
album title, no existing logos. Concept/role/brief explanations should be Japanese.
''' + TITLE_INSTRUCTIONS + LANGUAGE_INSTRUCTIONS

class AlbumManager:
    def __init__(self, service):
        self.s = service
        self.tasks = {}
        self.cover_tasks = {}
        self.video_tasks = {}
        self.export_lock = asyncio.Lock()
        self.cover_bridge = CodexBridge()
        self.root = service.JOBS.parent/'albums'
        self.root.mkdir(parents=True,exist_ok=True)
        self.items = {}
        for p in self.root.glob('*/album.json'):
            try:
                item=json.loads(p.read_text())
                if item['status'] in ('planning','generating'): item['status']='paused'
                if item.get('cover_status')=='generating': item['cover_status']='pending'
                if item.get('youtube',{}).get('status')=='uploading': item['youtube']['status']='interrupted'
                if item.get('video_status')=='generating': item['video_status']='interrupted'
                self.items[item['id']]=item
                self.save(item)
            except (OSError,ValueError,KeyError): pass

    def save(self, item):
        p=self.root/item['id']/'album.json';p.parent.mkdir(parents=True,exist_ok=True)
        temp=p.with_suffix('.tmp');temp.write_text(json.dumps(item,ensure_ascii=False,indent=2));temp.replace(p)

    def get(self, aid):
        if aid not in self.items: raise HTTPException(404,'アルバムが見つかりません')
        return self.items[aid]

    def public(self,item):
        result=dict(item)
        result['songs']=[self.s.public_job(self.s.jobs[j]) if j and j in self.s.jobs else None for j in item.get('song_ids',[])]
        result['deleted_count']=len(item.get('deleted_tracks',[]))
        result['completed']=sum(bool(j) and j['status']=='completed' for j in result['songs'])
        if item.get('cover_file'): result['cover_url']=f"/api/albums/{item['id']}/cover?v={item.get('cover_revision',0)}"
        return result

    async def create(self, request):
        if sum(x['status'] in ('planning','generating') for x in self.items.values())>=2:
            raise HTTPException(429,'同時に処理するアルバムは2枚までです')
        available=[engine for engine,status in self.s.engine_status(self.s.ROOT).items() if status['ready'] and engine!='mulacover' and (request.vocal_mode!='vocal' or engine!='stable-audio-3-medium')]
        if request.engine=='mixed':
            if len(available)<2: raise HTTPException(503,'混在には利用可能なモデルが2つ以上必要です')
        elif request.engine not in available: raise HTTPException(503,'モデルの準備が必要です')
        aid=secrets.token_hex(8)
        item={'id':aid,'title':'アルバム構成を作成中','status':'planning','request':request.model_dump(),
              'available_engines':available if request.engine=='mixed' else [request.engine],
              'song_ids':[],'created_at':time.time(),'cover_status':'pending' if request.generate_cover else 'disabled'}
        self.items[aid]=item;self.save(item);self.start(aid)
        return self.public(item)

    def resolve_track_engines(self, item, request, plan):
        for track in plan.tracks:
            if request.engine!='mixed':
                track.engine=request.engine
            elif track.engine not in item.get('available_engines',[]):
                raise ValueError('各曲に利用可能なモデルを割り当ててください')
            if track.engine=='stable-audio-3-medium' and track.vocal!='instrumental':
                raise ValueError('Stable Audio 3はインスト曲だけに割り当ててください')
        if request.engine=='mixed' and len({t.engine for t in plan.tracks})<2:
            raise ValueError('混在アルバムでは2種類以上のモデルを使ってください')

    def start(self, aid):
        self.tasks[aid]=asyncio.create_task(self.run(aid))

    async def run(self,aid):
        item=self.get(aid);request=AlbumInput(**item['request'])
        try:
            if 'plan' not in item:
                item['status']='planning';self.save(item)
                previous=[j['title'] for j in self.s.jobs.values()][-150:]
                if 'reference_research' not in item:
                    async with self.s.bridge.assist_lock:
                        item['reference_research']=await self.s.bridge.research_reference(AssistInput(
                            engine=next(e for e in item['available_engines'] if e!='stable-audio-3-medium') if request.engine=='mixed' else request.engine, brief=request.brief, reference_track='', model=request.model))
                    self.save(item)
                payload={**request.model_dump(),'recent_titles':previous,'reference_research':item['reference_research'],'available_engines':item.get('available_engines',[request.engine])}
                if request.duration_mode=='auto': payload['duration']=None
                for attempt in range(2):
                    instructions=PLAN_INSTRUCTIONS
                    if request.engine=='mixed':
                        instructions+='\nAssign each track an engine from available_engines and explain the choice in engine_reason. Use at least two different models. Choose by musical role and requested control: YuE2 uses a symbolic melody/harmony plan; ACE-Step supports vocals and instrumental tracks with numeric duration/BPM conditioning; Stable Audio 3 is instrumental-only with numeric duration and text tempo guidance. DiffSynth Music supports native text/lyrics generation with numeric BPM and duration; assign it to suitable original tracks. These interfaces do not guarantee superior quality for a genre. Preserve album cohesion. Never assign Stable Audio to a vocal track.\n'
                    else:
                        instructions+='\nUse the requested engine for every track; engine_reason can be empty.\n'
                    if request.engine in ('stable-audio-3-medium','mixed'):
                        guidance=STABLE_INSTRUCTIONS.split('## Official guidance',1)[1].split('## Studio behavior',1)[0]
                        instructions+='\nFor tracks assigned Stable Audio 3: each is a complete instrumental piece, not a stem. Name the lead instrument, groove and development. Use numeric track duration. Apply the following official prompt guidance when designing each brief:\n'+guidance
                    raw=await run_task(self.s.bridge,instructions,payload,ALBUM_SCHEMA,request.model)
                    try:
                        plan=AlbumPlan.model_validate(raw)
                        self.resolve_track_engines(item,request,plan)
                        if request.duration_mode=='auto' and len({t.duration for t in plan.tracks})<2:
                            raise ValueError('おまかせの曲長は役割・構成に応じて複数の長さを設計してください')
                        if request.duration_mode=='fixed':
                            for track in plan.tracks: track.duration=request.duration
                        if len(plan.tracks)!=request.track_count: raise ValueError('曲数が指定と一致しません')
                        voices={t.vocal for t in plan.tracks}
                        if request.vocal_mode=='mixed' and ('instrumental' not in voices or len(voices)==1): raise ValueError('歌声とインストを混在させてください')
                        if request.vocal_mode=='instrumental' and voices!={'instrumental'}: raise ValueError('全曲インストを指定してください')
                        if request.vocal_mode=='vocal' and 'instrumental' in voices: raise ValueError('全曲歌声ありを指定してください')
                        if any(similar_title(t.title,previous) for t in plan.tracks): raise ValueError('既存曲と似た曲名があります')
                        break
                    except ValueError as exc:
                        if attempt: raise
                        payload['revision_request']=str(exc)
                item.update(title=plan.title,plan=plan.model_dump(),song_ids=[None]*len(plan.tracks))
                self.save(item)
            plan=AlbumPlan(**item['plan']);self.resolve_track_engines(item,request,plan);item['status']='generating';item.pop('error',None);self.save(item)
            if request.generate_cover and item.get('cover_status') in ('pending','failed'):
                self.start_cover(aid)
            for index,track in enumerate(plan.tracks):
                if index in item.get('deleted_tracks',[]): continue
                jid=item['song_ids'][index]
                existing=self.s.jobs.get(jid) if jid else None
                if existing and existing['status']=='completed': continue
                if existing and existing['status'] in ('failed','cancelled','interrupted'):
                    # Resume/retry reuses the exact stored input and id; no duplicate completed tracks.
                    existing.update(status='queued');existing.pop('error',None);existing.pop('finished_at',None)
                    self.s.save_job(existing);self.s.queue.put_nowait(jid)
                if not existing:
                    context=f"ユーザーの元の依頼（音楽的な方向性の最優先条件）: {request.brief}\n\n以下は自動作成した案です。元の依頼と異なるジャンル・音作り・物語への脱線は修正してください。\nアルバム『{plan.title}』の{index+1}/{len(plan.tracks)}曲目。この曲の具体的な音楽案: {track.brief}\nこの曲の役割: {track.role}\n全体方針: {plan.concept}\n曲名: {track.title}\n他曲のタイトル: "+' / '.join(t.title for t in plan.tracks if t!=track)
                    seconds=track.duration if request.duration_mode=='auto' else request.duration
                    context=context[:5000]+f'\n曲の長さ: {seconds}秒（YuE2では目安）。最後の10〜15秒に終結の余白を確保。終わり方: {track.ending or "主題を回収し、解決感のある短いアウトロで終える"}。この時間内で完結する歌詞と構成、アウトロをスタイルに反映。'
                    song=SongInput(engine=track.engine,title=track.title,duration=seconds,
                        output_format=request.output_format,album_title=plan.title,track_number=index+1,
                        brief=context[:6000],auto_assist=True,language=request.language,assist_model=request.model,
                        # The planner's broad genre label is not an explicit user selection.
                        # Preserve its precise subgenre in the brief instead of imposing a preset.
                        choices=MusicChoices(genre="auto",bpm=track.bpm,vocal=track.vocal,melody="balanced"),
                        seed=secrets.randbelow(2147483648))
                    while True:
                        try: job=await self.s.create_song(song);break
                        except HTTPException as exc:
                            if exc.status_code!=429: raise
                            await asyncio.sleep(2)
                    jid=job['id'];item['song_ids'][index]=jid
                    self.s.jobs[jid].update(album_id=aid,track_number=index+1)
                    self.s.save_job(self.s.jobs[jid]);self.save(item)
                while self.s.jobs[jid]['status'] in self.s.IN_FLIGHT: await asyncio.sleep(2)
                if self.s.jobs[jid]['status']!='completed':
                    raise RuntimeError(f"{index+1}曲目で停止しました。詳細を確認して「再開」を押してください。")
            item['status']='completed';item['finished_at']=time.time();self.save(item)
        except asyncio.CancelledError:
            item['status']='paused';self.save(item);raise
        except Exception as exc:
            item.update(status='failed',error=str(exc) or 'Codexの構成生成がタイムアウトしました。再開で再試行できます。');self.save(item)

    def editable(self, item):
        if item['status'] in ('planning','generating') or item.get('cover_status')=='generating' or item.get('video_status')=='generating' or item.get('youtube',{}).get('status') in ('uploading','failed','interrupted'):
            raise HTTPException(409,'生成・書き出しの完了後に変更できます')

    def invalidate_video(self, item):
        for name in ('youtube.mp4','youtube-description.txt'):
            (self.root/item['id']/name).unlink(missing_ok=True)
        for key in ('video_status','video_error','video_seconds','video_bytes'):
            item.pop(key,None)

    def rename(self, aid, title):
        item=self.get(aid);self.editable(item)
        old=item['title']
        if title==old:return self.public(item)
        item['title']=title
        if 'plan' in item:
            item['plan']['title']=title
            item['plan']['cover_prompt']=item['plan']['cover_prompt'].replace(old,title)
        for jid in item.get('song_ids',[]):
            if jid and jid in self.s.jobs:
                self.s.jobs[jid]['album_title']=title;self.s.save_job(self.s.jobs[jid])
                path=self.s.JOBS/jid/'input.json'
                if path.exists():
                    data=json.loads(path.read_text());data['album_title']=title
                    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2));tmp.replace(path)
        self.invalidate_video(item);self.save(item)
        return self.public(item)

    def start_video(self, aid):
        item=self.get(aid);self.editable(item)
        if item['status']!='completed' or not item.get('cover_file'):
            raise HTTPException(409,'全曲とジャケットが完成してから書き出せます')
        if any(not t.done() for t in self.video_tasks.values()):
            raise HTTPException(409,'別の動画を書き出しています。完了後にお試しください')
        from album_video import render_video
        item['video_status']='generating';self.save(item)
        self.video_tasks[aid]=asyncio.create_task(render_video(self,aid))
        return self.public(item)

    def start_cover(self, aid):
        if aid in self.cover_tasks and not self.cover_tasks[aid].done(): return
        item=self.get(aid)
        item['cover_status']='generating';self.save(item)
        self.cover_tasks[aid]=asyncio.create_task(self.cover(aid))

    async def cover(self,aid):
        item=self.get(aid);item['cover_status']='generating';item.pop('cover_error',None);self.save(item)
        try:
            prompt=item['plan']['cover_prompt']+'\nCurrent album title (use this exact title if adding text): '+item['title']
            if item.get('cover_direction'): prompt+='\nNew visual direction: '+item['cover_direction']
            name=await generate_cover(self.cover_bridge,self.root/aid,prompt)
            self.invalidate_video(item)
            item['cover_revision']=item.get('cover_revision',0)+1
            item.update(cover_status='completed',cover_file=name);item.pop('cover_error',None)
        except asyncio.CancelledError:
            item['cover_status']='pending';raise
        except Exception as exc: item.update(cover_status='failed',cover_error=str(exc) or '画像生成がタイムアウトしました。再生成できます。')
        finally: self.save(item)

    async def pause(self,aid):
        item=self.get(aid)
        if item['status'] not in ('planning','generating'):
            raise HTTPException(409,'処理中のアルバムだけ一時停止できます')
        task=self.tasks.get(aid)
        if task and not task.done(): task.cancel();await asyncio.gather(task,return_exceptions=True)
        cover_task=self.cover_tasks.get(aid)
        if cover_task and not cover_task.done():
            cover_task.cancel();await asyncio.gather(cover_task,return_exceptions=True)
        for jid in item['song_ids']:
            if jid and self.s.jobs[jid]['status'] in self.s.IN_FLIGHT:
                await self.s.cancel(jid)
                while any(state and state[0] == jid for state in (getattr(self.s,'active',None),getattr(self.s,'preparation',None))):
                    await asyncio.sleep(.05)
        item['status']='paused';self.save(item)
        return self.public(item)

    async def resume(self,aid):
        item=self.get(aid)
        if item['status'] not in ('paused','failed'): raise HTTPException(409,'このアルバムは再開できません')
        if sum(x['status'] in ('planning','generating') for x in self.items.values())>=2: raise HTTPException(429,'処理中のアルバムの完了をお待ちください')
        item['status']='generating';self.save(item);self.start(aid)
        return self.public(item)

    def export(self,aid):
        item=self.get(aid)
        if item['status']!='completed': raise HTTPException(409,'全曲の完成後にダウンロードできます')
        if item.get('cover_status')=='generating': raise HTTPException(409,'ジャケットの完成をお待ちください')
        folder=self.root/aid;out=folder/'album.zip';tmp=folder/'album.zip.tmp'
        playlist=['#EXTM3U']
        booklet=[f"# {item['title']}", '', item['plan']['concept'], '', f"Model: {item['request']['engine']} / Codexによる構成・入力支援", '']
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED) as z:
            z.writestr('album.json',json.dumps(self.public(item),ensure_ascii=False,indent=2))
            for i,jid in enumerate(item['song_ids']):
                if i in item.get('deleted_tracks',[]): continue
                song_folder=self.s.JOBS/jid;name=stored_audio(song_folder)
                if not name: raise RuntimeError('保存音声が見つかりません')
                title=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',self.s.jobs[jid]['title'])[:100]
                base=f'{i+1:02d} - {title}'
                filename=base+Path(name).suffix
                z.write(song_folder/name,filename)
                seconds=self.s.jobs[jid].get('summary',{}).get('audio_seconds',0)
                playlist.extend([f"#EXTINF:{round(seconds)},{self.s.jobs[jid]['title']}",filename])
                track=item['plan']['tracks'][i]
                booklet.extend([f"## {i+1:02d}. {track['title']}",'',f"{track['bpm']} BPM / {track['vocal']} / {round(seconds)}秒 / {track.get('engine') or item['request']['engine']}",'',track['role'],''])
                original=json.loads((song_folder/'input.json').read_text())
                z.writestr(base+'.txt',original['style']+'\n\n'+original['lyrics'])
            if item.get('cover_file'): z.write(folder/item['cover_file'],item['cover_file'])
            z.writestr('cover-prompt.txt',item['plan']['cover_prompt'])
            z.writestr('playlist.m3u8','\n'.join(playlist)+'\n')
            z.writestr('booklet.md','\n'.join(booklet))
        tmp.replace(out)
        return out

    async def close(self):
        tasks=[*self.tasks.values(),*self.cover_tasks.values(),*self.video_tasks.values()]
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await self.cover_bridge.close()
