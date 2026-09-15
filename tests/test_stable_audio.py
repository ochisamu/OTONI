import asyncio
import json
from unittest.mock import AsyncMock
import pytest
from schemas import SongInput,AssistInput
from album_schemas import AlbumInput
from engines import worker_command,engine_status
from stable_audio_support import ENGINE,music_prompt
import app as service


def test_stable_is_instrumental_and_not_yue_or_ace():
    s=SongInput(engine=ENGINE,lyrics='previous sung words',style='Jazz')
    assert s.choices.vocal=='instrumental' and s.lyrics=='[Instrumental]' and s.cot=='off'
    assert 'previous sung words' not in music_prompt(s) and '[Instrumental]' not in music_prompt(s)
    with pytest.raises(ValueError):SongInput(engine=ENGINE,choices={'vocal':'male'})
    with pytest.raises(ValueError):SongInput(engine=ENGINE,abc='X:1')
    assert AlbumInput(engine=ENGINE,brief='Instrumental album').vocal_mode=='instrumental'
    assist=AssistInput(engine=ENGINE,brief='Jazz instrumental',current_lyrics='old words',current_abc='old score')
    assert not assist.current_lyrics and not assist.current_abc and not assist.preserve_lyrics


def test_auto_duration_preparation_and_worker(tmp_path,monkeypatch):
    compose=AsyncMock(return_value={'title':'Piano study','style':'Instrumental jazz, 95 BPM','lyrics':'[Instrumental]','duration':95,'bpm':95})
    monkeypatch.setattr(service.bridge,'compose',compose)
    song=SongInput(engine=ENGINE,title='Piano study',duration_mode='auto')
    resolved=asyncio.run(service.prepare_song(tmp_path,song))
    assert resolved.duration==95 and resolved.duration_mode=='fixed'
    assert '95 BPM' in music_prompt(resolved)
    assert 'worker_stable.py' in worker_command(tmp_path,ENGINE,tmp_path)[2]
    assert not engine_status(tmp_path)[ENGINE]['ready']
    assert json.loads((tmp_path/'input.json').read_text())['engine']==ENGINE


def test_codex_desktop_update_can_relocate_binary(tmp_path,monkeypatch):
    from codex_bridge import resolve_codex_command
    root=tmp_path/'wsl';new=root/'new'/'codex';new.parent.mkdir(parents=True)
    new.write_text('test');new.chmod(0o700)
    monkeypatch.setenv('YUE_CODEX_BIN',str(root/'old'/'codex'))
    assert resolve_codex_command()==str(new)
