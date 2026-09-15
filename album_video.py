"""Local YouTube-ready album video export; no account connection or publishing."""
import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from audio_storage import stored_audio, probe
from video_artwork import title_card


def timestamp(seconds):
    n=int(seconds)
    return f'{n//3600}:{n//60%60:02}:{n%60:02}' if n>=3600 else f'{n//60:02}:{n%60:02}'


async def render_video(manager, aid):
    item=manager.get(aid)
    folder=manager.root/aid
    proc=None
    output=folder/'youtube.tmp.mp4'
    item.update(video_status='generating');item.pop('video_error',None);manager.save(item)
    try:
        with tempfile.TemporaryDirectory(prefix='video-',dir=folder) as temp:
            temp=Path(temp)
            cover=temp/'cover.png'
            shutil.copyfile(folder/item['cover_file'],cover)
            args=['ffmpeg','-nostdin','-v','error','-y','-filter_complex_threads','1',
                  '-f','concat','-safe','0','-i',str(temp/'frames.txt')]
            filters=[];chapters=[];total=0;frames=[]
            track_count=sum(i not in item.get('deleted_tracks',[]) for i in range(len(item['song_ids'])))
            for index,jid in enumerate(item['song_ids']):
                if index in item.get('deleted_tracks',[]):continue
                source=manager.s.JOBS/jid
                name=stored_audio(source)
                if not name:raise RuntimeError('収録曲の音声が見つかりません')
                audio=temp/f'{len(chapters)}{Path(name).suffix}'
                # A snapshot survives storage conversions without duplicating audio bytes.
                audio.hardlink_to(source/name)
                seconds,_,_=await asyncio.to_thread(probe,audio)
                title=manager.s.jobs[jid]['title']
                card=temp/f'card-{len(chapters):02d}.png'
                await asyncio.to_thread(title_card,cover,item['title'],title,len(chapters)+1,track_count,card)
                frames.extend([f"file '{card.name}'", f'duration {seconds:.9f}'])
                chapters.append(f'{timestamp(total)} {title}')
                total+=seconds
                n=len(chapters)
                args+=['-i',str(audio)]
                filters.append(f'[{n}:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a{n}]')
            if not chapters:raise RuntimeError('収録曲がありません')
            frames.extend([f"file '{card.name}'"])
            (temp/'frames.txt').write_text('ffconcat version 1.0\n'+'\n'.join(frames)+'\n')
            filters.append(''.join(f'[a{i}]' for i in range(1,len(chapters)+1))+f'concat=n={len(chapters)}:v=0:a=1[a]')
            filters.append('[0:v]fps=24,setsar=1,format=yuv420p[v]')
            args+=['-filter_complex',';'.join(filters),'-map','[v]','-map','[a]',
                   '-c:v','libx264','-threads','2','-preset','veryfast','-tune','stillimage','-crf','20',
                   '-c:a','aac','-b:a','320k','-ar','48000','-t',str(total),'-movflags','+faststart',
                   '-metadata',f'title={item["title"]}',str(output)]
            proc=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.PIPE)
            _,err=await proc.communicate()
            if proc.returncode:raise RuntimeError('動画の書き出しに失敗しました: '+err.decode(errors='replace')[-1200:])
            duration,_,_=await asyncio.to_thread(probe,output)
            if abs(duration-total)>.5:raise RuntimeError('動画と収録曲の長さが一致しません')
            output.replace(folder/'youtube.mp4')
            description=f'{item["title"]}\n\n{item["plan"]["concept"]}\n\nTRACKLIST\n'+ '\n'.join(chapters)
            engines=list(dict.fromkeys(manager.s.jobs[jid].get('engine',item['request']['engine']) for i,jid in enumerate(item['song_ids']) if i not in item.get('deleted_tracks',[]) and jid))
            names={'yue2':'YuE2','ace-xl-turbo':'ACE-Step','stable-audio-3-medium':'Stable Audio 3 Medium','diffsynth-music':'DiffSynth Music','mulacover':'MuLaCover'}
            description+='\n\nMusic created with '+', '.join(names.get(e,e) for e in engines)+' / OTONI\n'
            (folder/'youtube-description.txt').write_text(description)
            item.update(video_status='completed',video_seconds=duration,video_bytes=(folder/'youtube.mp4').stat().st_size)
    except asyncio.CancelledError:
        if proc and proc.returncode is None:
            proc.terminate();await proc.wait()
        item.update(video_status='interrupted')
        raise
    except Exception as exc:
        item.update(video_status='failed',video_error=str(exc))
    finally:
        output.unlink(missing_ok=True)
        manager.save(item)
