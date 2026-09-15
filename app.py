import asyncio
import json
import os
import re
import secrets
import signal
import shutil
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from codex_bridge import CodexBridge
from schemas import AssistInput, SongInput, MusicChoices
from prompting import GUIDE_REVISION, GUIDE_URL, preset_style, enforce_instrumental
from engines import engine_status, worker_command, ACE_GUIDE_URL
from stable_audio_support import GUIDE as STABLE_GUIDE
from audio_storage import stored_audio, finalize_audio
from title_variety import similar_title
from album_schemas import AlbumInput, AlbumRename, CoverRequest
from pydantic import BaseModel
from typing import Literal
from albums import AlbumManager
from derivations import source_files, snapshot_source

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("YUE_DATA_DIR", ROOT / "data"))
JOBS = DATA / "songs"
JOBS.mkdir(parents=True, exist_ok=True)
(ROOT / "work").mkdir(exist_ok=True)
bridge = CodexBridge()
jobs = {}
queue = asyncio.Queue()
active = None
preparation = None
IN_FLIGHT = ("queued", "preparing", "running")
assist_jobs = {}
assist_tasks = set()
album_manager = None
storage_lock = asyncio.Lock()


def save_job(job):
    path = JOBS / job["id"] / "job.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2))
    tmp.replace(path)


def log_tail(folder):
    path = folder / "generation.log"
    if not path.exists():
        return ""
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 7000))
        text = stream.read().decode("utf-8", errors="replace")
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).replace("\r", "\n")


def public_job(job, detail=False):
    result = dict(job)
    folder = JOBS / job["id"]
    if detail:
        result["log"] = log_tail(folder)
        result["input"] = json.loads((folder / "input.json").read_text())
        if (folder / "assistance.json").is_file():
            result["assistance"] = json.loads((folder / "assistance.json").read_text())
    if (folder / 'derivation.json').is_file():
        result['derivation'] = json.loads((folder / 'derivation.json').read_text())
    if job["status"] == "completed":
        name = stored_audio(folder)
        if name:
            result['audio_url'] = f'/api/songs/{job["id"]}/file/{Path(name).name}'
            result['audio_format'] = Path(name).suffix[1:]
        if (folder/'storage.json').is_file(): result['storage'] = json.loads((folder/'storage.json').read_text())
    return result


async def terminate(proc):
    if proc and proc.returncode is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(proc.wait(), 8)
        except TimeoutError:
            os.killpg(proc.pid, signal.SIGKILL)
            await proc.wait()


async def prepare_song(folder, request):
    album_id=jobs.get(folder.name,{}).get('album_id')
    shared_research=album_manager.items.get(album_id,{}).get('reference_research') if album_manager and album_id else None
    research_kwargs = {"reference_research": shared_research} if shared_research is not None else {}
    if request.auto_assist:
        result = await bridge.compose(AssistInput(
            engine=request.engine, duration=request.duration, duration_mode=request.duration_mode,
            recent_titles=[j["title"] for j in jobs.values()][-150:],
            brief=request.brief.strip() or "選択した曲調に合う、自然で印象に残る曲を作ってください。",
            current_style=request.style, current_lyrics=request.lyrics,
            preserve_lyrics=bool(request.lyrics.strip()), language=request.language, model=request.assist_model,
            choices=request.choices, current_abc=request.abc, reference_track=request.reference_track), **research_kwargs)
        if not request.title.strip() or request.title == 'Untitled':
            recent=[j['title'] for j in jobs.values()][-150:]
            if similar_title(result['title'], recent):
                result = await bridge.compose(AssistInput(engine=request.engine, duration=request.duration, duration_mode=request.duration_mode,
                    brief=(request.brief + '\n既存曲と似ない、具体的で異なる題名を作ってください。')[:6000],
                    current_style=result['style'],current_lyrics=result['lyrics'],preserve_lyrics=True,
                    choices=request.choices,language=request.language,model=request.assist_model,
                    current_abc=request.abc,reference_track=request.reference_track,
                    recent_titles=recent+[result['title']]), **research_kwargs)
                if similar_title(result['title'],recent): raise ValueError('曲名が既存曲と似すぎています。題名を指定して再試行してください。')
        (folder / "assistance.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        update = {"style": result["style"], "lyrics": result["lyrics"], "auto_assist": False}
        if request.choices.bpm is None and result.get("bpm") is not None and request.derivation_mode not in ("score", "cover"):
            update["choices"] = request.choices.model_copy(update={"bpm":result["bpm"]}).model_dump()
        if request.duration_mode == "auto":
            update.update(duration=result["duration"], duration_mode="fixed")
        if request.choices.vocal == "instrumental":
            update["lyrics"] = "[Instrumental]"
        elif request.lyrics.strip():
            update["lyrics"] = request.lyrics
        if not request.title.strip() or request.title == "Untitled":
            update["title"] = result["title"]
        request = SongInput.model_validate({**request.model_dump(), **update})
    elif request.choices.vocal == "instrumental":
        request = SongInput.model_validate({**request.model_dump(),
            "style": enforce_instrumental(request.style.strip() or preset_style(request.choices, request.language)),
            "lyrics": "[Instrumental]"})
    (folder / "input.json").write_text(request.model_dump_json(indent=2))
    return request


async def run_queue():
    global active, preparation
    while True:
        jid = await queue.get()
        job = jobs[jid]
        proc = None
        try:
            if job["status"] != "queued":
                continue
            folder = JOBS / jid
            request = SongInput.model_validate_json((folder / "input.json").read_text())
            job.update(status="preparing" if request.auto_assist else "running", started_at=time.time())
            save_job(job)
            prep = asyncio.create_task(prepare_song(folder, request))
            preparation = (jid, prep)
            try:
                request = await prep
            except asyncio.CancelledError:
                if job["status"] == "cancelled" and not asyncio.current_task().cancelling():
                    continue
                raise
            finally:
                preparation = None
            if job["status"] == "cancelled":
                continue
            job.update(status="running", title=request.title, prepared_at=time.time(),
                       auto_assisted=(folder / "assistance.json").is_file())
            save_job(job)
            with (folder / "generation.log").open("wb") as log:
                proc = await asyncio.create_subprocess_exec(
                    *worker_command(ROOT, request.engine, folder),
                    stdout=log, stderr=log, cwd=ROOT, start_new_session=True)
                active = (jid, proc)
                if job["status"] == "cancelled":
                    await terminate(proc)
                await proc.wait()
            if job["status"] == "cancelled":
                pass
            elif proc.returncode == 0 and (folder / "summary.json").is_file():
                job.update(status="completed", summary=json.loads((folder / "summary.json").read_text()))
            else:
                tail = log_tail(folder)
                error = "VRAM不足です。他のGPUアプリを閉じてから再実行してください。" if "out of memory" in tail.lower() else "生成に失敗しました。詳細ログを確認してください。"
                job.update(status="failed", error=error)
            if job["status"] == "completed":
                job["summary"]["total_seconds"] = round(time.time() - job["started_at"], 2)
        except asyncio.CancelledError:
            await terminate(proc)
            job.update(status="interrupted", error="サーバー停止により中断されました。履歴から再生成できます。")
            raise
        except Exception as exc:
            job.update(status="failed", error=str(exc))
        finally:
            active = None
            job["finished_at"] = time.time()
            save_job(job)
            queue.task_done()


@asynccontextmanager
async def lifespan(app):
    global album_manager
    for path in JOBS.glob("*/job.json"):
        try:
            job = json.loads(path.read_text())
            if job["status"] in IN_FLIGHT:
                job.update(status="interrupted", error="前回のサーバー終了で中断されました。入力を再利用してください。")
                save_job(job)
            jobs[job["id"]] = job
        except (ValueError, KeyError, OSError):
            continue
    album_manager = AlbumManager(sys.modules[__name__])
    task = asyncio.create_task(run_queue())
    yield
    await close_youtube()
    await album_manager.close()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    for pending in list(assist_tasks):
        pending.cancel()
    await asyncio.gather(*assist_tasks, return_exceptions=True)
    await bridge.close()


app = FastAPI(title="YuE2 Studio", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"] +
                   [host.strip() for host in os.environ.get("YUE_ALLOWED_HOSTS", "").split(",") if host.strip()])


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "別サイトからの操作は受け付けません"}, status_code=403)
        if request.headers.get("x-yue-request") != "studio":
            return JSONResponse({"detail": "Missing local request header"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
async def index():
    return FileResponse(ROOT / "web/index.html")


@app.get("/api/status")
async def status():
    gpu = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "/usr/lib/wsl/lib/nvidia-smi" if Path("/usr/lib/wsl/lib/nvidia-smi").exists() else "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        out, _ = await asyncio.wait_for(proc.communicate(), 5)
        name, total, used = out.decode().splitlines()[0].split(",")
        gpu = {"name": name.strip(), "total_mib": int(total), "used_mib": int(used)}
    except (OSError, ValueError, IndexError, TimeoutError):
        pass
    ready = all((ROOT / "models" / name / ".ready").is_file() for name in ("YuE2-3B", "YuE2-Vae"))
    return {"models_ready": ready, "engines": engine_status(ROOT), "gpu": gpu, "active_id": active[0] if active else preparation[0] if preparation else None,
            "queued": sum(j["status"] == "queued" for j in jobs.values()), "precision": "BF16 / VAE FP32"}


@app.get("/api/account")
async def account():
    try:
        result = await bridge.rpc("account/read", {"refreshToken": False})
        return {"available": True, **result}
    except Exception as exc:
        return {"available": False, "account": None, "error": str(exc)}


@app.get("/api/models")
async def models():
    try:
        return await bridge.rpc("model/list", {"includeHidden": False})
    except Exception as exc:
        raise HTTPException(503, str(exc))


@app.post("/api/login")
async def login():
    try:
        return await bridge.rpc("account/login/start", {"type": "chatgpt"})
    except Exception as exc:
        raise HTTPException(503, str(exc))


@app.get("/api/songs")
async def list_songs():
    return [public_job(j) for j in sorted(jobs.values(), key=lambda j: j["created_at"], reverse=True)]


@app.post("/api/preset")
async def preset(request: AssistInput):
    return {"style": preset_style(request.choices, request.language),
            "lyrics": "[Instrumental]" if request.choices.vocal == "instrumental" else "",
            "guide_url": STABLE_GUIDE if request.engine == "stable-audio-3-medium" else ACE_GUIDE_URL if request.engine == "ace-xl-turbo" else GUIDE_URL}


@app.post("/api/songs", status_code=202)
async def create_song(request: SongInput):
    if not engine_status(ROOT)[request.engine]["ready"]:
        script = "setup_stable.sh（画面の導入手順で利用条件とアクセス権を確認）" if request.engine == "stable-audio-3-medium" else "setup_ace.sh" if request.engine == "ace-xl-turbo" else "setup.sh"
        raise HTTPException(503, f"選択モデルの準備が完了していません。scripts/{script}を実行してください。")
    if sum(j["status"] in IN_FLIGHT for j in jobs.values()) >= 4:
        raise HTTPException(429, "生成待ちは最大4曲です。完了してから追加してください。")
    source = source_files(JOBS, jobs, request)
    jid = secrets.token_hex(8)
    folder = JOBS / jid
    folder.mkdir()
    (folder / "submitted.json").write_text(request.model_dump_json(indent=2))
    async with storage_lock:
        if sum(j["status"] in IN_FLIGHT for j in jobs.values()) >= 4:
            (folder / 'submitted.json').unlink()
            folder.rmdir()
            raise HTTPException(429, "生成待ちは最大4曲です。完了してから追加してください。")
        # Re-resolve after acquiring the conversion lock; a stored format may change.
        source = source_files(JOBS, jobs, request)
        request = await asyncio.to_thread(snapshot_source, folder, request, source)
    (folder / "input.json").write_text(request.model_dump_json(indent=2))
    job = {"id": jid, "title": request.title or "Untitled", "status": "queued",
           "seed": request.seed, "cot": request.cot, "engine": request.engine, "created_at": time.time()}
    jobs[jid] = job
    save_job(job)
    queue.put_nowait(jid)
    return public_job(job)


class DerivativeDraft(BaseModel):
    mode: Literal["score", "cover", "timbre", "diffsynth", "mulacover"]


@app.post("/api/songs/{jid}/derive")
async def derivative_draft(jid: str, options: DerivativeDraft):
    original = get_job(jid)
    if original['status'] != 'completed':
        raise HTTPException(400, '完成した曲から派生を作成してください')
    data = json.loads((JOBS/jid/'input.json').read_text())
    score = options.mode == 'score'
    control=options.mode in ('diffsynth','mulacover')
    data.update(engine=('diffsynth-music' if options.mode=='diffsynth' else 'mulacover') if control else 'yue2' if score else 'ace-xl-turbo', ace_lm='none',
        source_song_id=jid, derivation_mode='control' if control else options.mode, control_mode='reference' if control else 'native', duration_mode='fixed', reference_strength=0.8,
        title=original['title'][:100]+'・別テイク', album_title='', track_number=None,
        abc='', cot='full', cfg_scale=None, auto_assist=True, reference_track='',
        brief='元曲の良いところを保ち、編成や音色を調整した別テイクを作る。変更したい点：',
        seed=secrets.randbelow(2147483648))
    if not score and not control and len(data['lyrics']) > 4096:
        raise HTTPException(400, 'ACE-Step用には歌詞が長すぎます。YuE2の譜面派生を使うか、歌詞を短くした入力から作成してください')
    if options.mode == 'timbre':
        data.update(lyrics='', brief='元曲の音色・ミックス・雰囲気を参考に、新しい旋律と歌詞の曲を作る。変更したい点：')
    request = SongInput(**data)
    source = source_files(JOBS, jobs, request)
    if score:
        from tempo_control import score_bpm
        data['abc'] = source[1].read_text()
        bpm=score_bpm(data['abc'])
        if bpm is not None and 40 <= bpm <= 220: data['choices'].update(bpm=bpm,tempo='auto')
    return {'input': data, 'source_title': original['title']}


def get_job(jid):
    if jid not in jobs:
        raise HTTPException(404, "曲が見つかりません")
    return jobs[jid]


@app.get("/api/songs/{jid}")
async def song(jid: str):
    return public_job(get_job(jid), detail=True)


@app.post("/api/songs/{jid}/cancel")
async def cancel(jid: str):
    job = get_job(jid)
    if job["status"] not in IN_FLIGHT:
        raise HTTPException(409, "この曲の処理は終了しています")
    job.update(status="cancelled", finished_at=time.time())
    save_job(job)
    if active and active[0] == jid:
        await terminate(active[1])
    if preparation and preparation[0] == jid:
        preparation[1].cancel()
    return public_job(job)


@app.get("/api/songs/{jid}/file/{name}")
async def file(jid: str, name: str):
    job = get_job(jid)
    allowed = {"song.wav": "song.wav", "audio.flac": "audio.flac" if (JOBS / jid / "audio.flac").is_file() else "artifacts/audio.flac",
               "audio.m4a": "audio.m4a",
               "score.abc": "artifacts/score.abc", "input.json": "input.json",
               "result.json": "artifacts/result.json", "submitted.json": "submitted.json",
               "assistance.json": "assistance.json"}
    if name not in allowed or (name not in ("input.json", "submitted.json", "assistance.json") and job["status"] != "completed"):
        raise HTTPException(404)
    path = JOBS / jid / allowed[name]
    if not path.is_file():
        raise HTTPException(404, "この生成結果には譜面がありません")
    return FileResponse(path, filename=name)


@app.post("/api/assist", status_code=202)
async def assist(request: AssistInput):
    request = request.model_copy(update={"recent_titles": [j["title"] for j in jobs.values()][-150:]})
    if any(j["status"] == "running" for j in assist_jobs.values()):
        raise HTTPException(429, "入力支援が実行中です。完了をお待ちください。")
    # Bound retained drafts in this local process.
    if len(assist_jobs) >= 30:
        assist_jobs.pop(next(iter(assist_jobs)))
    aid = secrets.token_hex(8)
    assist_jobs[aid] = {"id": aid, "status": "running"}

    async def run():
        try:
            result = await bridge.compose(request)
            assist_jobs[aid].update(status="completed", result=result)
        except TimeoutError:
            assist_jobs[aid].update(status="failed", error="入力支援がタイムアウトしました。もう一度お試しください。")
        except Exception as exc:
            assist_jobs[aid].update(status="failed", error=str(exc))
    task = asyncio.create_task(run())
    assist_tasks.add(task)
    task.add_done_callback(assist_tasks.discard)
    return assist_jobs[aid]


@app.get("/api/assist/{aid}")
async def assist_result(aid: str):
    if aid not in assist_jobs:
        raise HTTPException(404, "入力支援の結果が見つかりません。再実行してください。")
    return assist_jobs[aid]


class StorageInput(BaseModel):
    format: Literal['m4a','flac'] = 'm4a'

@app.post('/api/songs/{jid}/storage')
async def convert_song(jid: str, request: StorageInput):
    job=get_job(jid)
    if job['status']!='completed': raise HTTPException(409,'完成した曲だけ変換できます')
    async with storage_lock:
        result=await asyncio.to_thread(finalize_audio,JOBS/jid,request.format,job['title'])
    return result

class DeleteSongInput(BaseModel):
    title: str

@app.post('/api/songs/{jid}/delete')
async def delete_song(jid: str, request: DeleteSongInput):
    async with (album_manager.export_lock if album_manager else asyncio.Lock()):
        async with storage_lock:
            job=get_job(jid)
            if request.title != job['title']:
                raise HTTPException(409,'曲名が変わりました。確認し直してください')
            if job['status'] in IN_FLIGHT or any(state and state[0]==jid for state in (active,preparation)):
                raise HTTPException(409,'生成中・待機中の曲は、キャンセルして処理が終了してから削除してください')
            affected=[a for a in album_manager.items.values() if jid in a.get('song_ids',[])] if album_manager else []
            if any(a['status'] in ('planning','generating') or a.get('video_status')=='generating' or a.get('youtube',{}).get('status') in ('uploading','failed','interrupted') for a in affected):
                raise HTTPException(409,'このアルバムの生成を一時停止してから削除してください')
            folder=JOBS/jid
            if folder.is_dir(): shutil.rmtree(folder)
            for album in affected:
                indices=[i for i,value in enumerate(album['song_ids']) if value==jid]
                album['deleted_tracks']=sorted(set(album.get('deleted_tracks',[])+indices))
                for i in indices: album['song_ids'][i]=None
                album_manager.invalidate_video(album)
                album_manager.save(album)
                (album_manager.root/album['id']/'album.zip').unlink(missing_ok=True)
            del jobs[jid]
    return {'deleted':jid}

@app.get('/api/albums')
async def list_albums():
    return [album_manager.public(a) for a in sorted(album_manager.items.values(),key=lambda a:a['created_at'],reverse=True)]

@app.post('/api/albums',status_code=202)
async def create_album(request: AlbumInput):
    return await album_manager.create(request)

@app.get('/api/albums/{aid}')
async def album(aid: str):
    return album_manager.public(album_manager.get(aid))

@app.post('/api/albums/{aid}/pause')
async def pause_album(aid: str):
    return await album_manager.pause(aid)

@app.post('/api/albums/{aid}/resume')
async def resume_album(aid: str):
    return await album_manager.resume(aid)

@app.post('/api/albums/{aid}/cover',status_code=202)
async def remake_cover(aid: str, request: CoverRequest):
    item=album_manager.get(aid)
    if 'plan' not in item: raise HTTPException(409,'構成の完成をお待ちください')
    album_manager.editable(item)
    item['cover_direction']=request.direction
    album_manager.start_cover(aid)
    return album_manager.public(item)

@app.get('/api/albums/{aid}/cover')
async def album_cover(aid: str):
    item=album_manager.get(aid)
    if not item.get('cover_file'): raise HTTPException(404,'ジャケット生成前です')
    return FileResponse(album_manager.root/aid/item['cover_file'])

@app.post('/api/albums/{aid}/rename')
async def rename_album(aid: str, request: AlbumRename):
    async with album_manager.export_lock:
        async with storage_lock:
            return album_manager.rename(aid,request.title)

@app.post('/api/albums/{aid}/video',status_code=202)
async def make_album_video(aid: str):
    return album_manager.start_video(aid)

@app.get('/api/albums/{aid}/video/{name}')
async def download_album_video(aid: str, name: str):
    item=album_manager.get(aid)
    allowed={'youtube.mp4':'video/mp4','youtube-description.txt':'text/plain'}
    if name not in allowed or item.get('video_status')!='completed':
        raise HTTPException(404,'書き出しの完成をお待ちください')
    return FileResponse(album_manager.root/aid/name,filename=name,media_type=allowed[name])

@app.get('/api/albums/{aid}/download')
async def album_download(aid: str):
    async with album_manager.export_lock:
        path=await asyncio.to_thread(album_manager.export,aid)
    return FileResponse(path,filename=f'album-{aid}.zip',media_type='application/zip')


from youtube_publish import install_youtube
close_youtube = install_youtube(app, lambda: album_manager, ROOT/'data'/'private-youtube')

app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
