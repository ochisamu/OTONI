"""Validated album requests and track sequencing plans."""
from language_policy import LyricLanguage
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from title_variety import similar_title

class AlbumInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    brief: str = Field(min_length=5, max_length=6000)
    engine: Literal['yue2','ace-xl-turbo','stable-audio-3-medium','mixed'] = 'yue2'
    track_count: int = Field(default=10, ge=2, le=20)
    duration: int = Field(default=180, ge=30, le=180)
    duration_mode: Literal['fixed','auto'] = 'fixed'
    vocal_mode: Literal['mixed','vocal','instrumental'] = 'mixed'
    language: LyricLanguage = '日本語'
    output_format: Literal['m4a','flac'] = 'm4a'
    model: str = Field(default='', max_length=100)
    generate_cover: bool = True

    @model_validator(mode='after')
    def instrumental_engine(self):
        if self.engine=='stable-audio-3-medium': self.vocal_mode='instrumental'
        return self

class AlbumTrack(BaseModel):
    engine: Literal['yue2','ace-xl-turbo','stable-audio-3-medium'] | None = None
    engine_reason: str = Field(default='', max_length=500)
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=120)
    duration: int = Field(default=180, ge=30, le=180)
    ending: str = Field(default='', max_length=500)
    role: str = Field(min_length=1, max_length=500)
    brief: str = Field(min_length=5, max_length=2500)
    bpm: int = Field(ge=40, le=220)
    vocal: Literal['female','male','instrumental']
    genre: Literal['pop','citypop','rock','acoustic','jazz','rnb','lofi','edm','ambient','orchestral','metal']

class AlbumPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1,max_length=120)
    concept: str = Field(min_length=10,max_length=4000)
    cover_prompt: str = Field(min_length=30,max_length=3000)
    tracks: list[AlbumTrack] = Field(min_length=2,max_length=20)
    @model_validator(mode='after')
    def distinct(self):
        titles=[]
        for t in self.tracks:
            if similar_title(t.title,titles): raise ValueError('似すぎた曲名があります。構成を再作成してください')
            titles.append(t.title)
        return self

# Strict structured output requires every property to be required.
ALBUM_SCHEMA = AlbumPlan.model_json_schema()
for obj in [ALBUM_SCHEMA, *ALBUM_SCHEMA.get('$defs',{}).values()]:
    if obj.get('type')=='object': obj['required']=list(obj['properties'])

class AlbumRename(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120, pattern=r'^[^\x00-\x1f\x7f]+$')

class CoverRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    direction: str = Field(default='', max_length=2000)
