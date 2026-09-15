import json
from pathlib import Path
import pytest
from schemas import SongInput,AssistInput
from album_schemas import AlbumInput
from engines import worker_command
from derivations import source_files,snapshot_source


def test_control_validation_and_worker_routing(tmp_path):
    with pytest.raises(ValueError,match='元曲'):SongInput(engine='mulacover',auto_assist=True)
    with pytest.raises(ValueError,match='元曲'):SongInput(engine='diffsynth-music',control_mode='reference',auto_assist=True)
    with pytest.raises(ValueError):SongInput(engine='ace-xl-turbo',control_mode='beats',auto_assist=True)
    for engine in ['mulacover','diffsynth-music']:
        request=SongInput(engine=engine,source_song_id='a'*16,derivation_mode='control',control_mode='reference',auto_assist=True)
        assert request.cot=='off'
        assert worker_command(tmp_path,engine,tmp_path/'job')[-2].endswith('worker_control.py')
        assert AssistInput(engine=engine,brief='新しい曲').engine==engine
    request=SongInput(engine='diffsynth-music',control_mode='beats',auto_assist=True,duration_mode='auto')
    assert request.duration_mode=='auto'
    with pytest.raises(ValueError):AlbumInput(engine='mulacover',brief='アルバムの生成')
    assert AlbumInput(engine='diffsynth-music',brief='アルバムの生成').engine=='diffsynth-music'


def test_control_reference_is_snapshotted(tmp_path):
    from fastapi import HTTPException
    jobs=tmp_path/'songs';sid='a'*16;origin=jobs/sid;origin.mkdir(parents=True)
    (origin/'audio.m4a').write_bytes(b'test-reference')
    new=tmp_path/'new';new.mkdir()
    req=SongInput(engine='mulacover',source_song_id=sid,derivation_mode='control',auto_assist=True)
    with pytest.raises(HTTPException):source_files(jobs,{},req)
    source=source_files(jobs,{sid:{'status':'completed','title':'Original'}},req)
    snapshot_source(new,req,source)
    metadata=json.loads((new/'derivation.json').read_text())
    assert (new/metadata['audio_file']).read_bytes()==b'test-reference'
    assert metadata['source_song_id']==sid
