from language_policy import LyricLanguage
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MusicChoices(BaseModel):
    model_config = ConfigDict(extra="forbid")
    genre: Literal["auto", "pop", "citypop", "rock", "acoustic", "jazz", "rnb", "lofi", "edm", "ambient", "orchestral", "metal"] = "auto"
    tempo: Literal["auto", "slow", "medium", "fast"] = "auto"
    bpm: int | None = Field(default=None, ge=40, le=220)
    vocal: Literal["auto", "female", "male", "instrumental"] = "auto"
    mood: Literal["auto", "hopeful", "sad", "energetic", "calm", "dark"] = "auto"
    melody: Literal["balanced", "catchy", "lyrical", "dramatic"] = "catchy"


class SongInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: Literal["yue2", "ace-xl-turbo", "stable-audio-3-medium"] = "yue2"
    ace_lm: Literal["none", "1.7B"] = "none"
    source_song_id: str = Field(default="", pattern=r"^(?:[a-f0-9]{16})?$")
    derivation_mode: Literal["none", "score", "cover", "timbre"] = "none"
    reference_strength: float = Field(default=0.8, ge=0.0, le=1.0)
    duration: int = Field(default=60, ge=10, le=180)
    duration_mode: Literal["fixed", "auto"] = "fixed"
    output_format: Literal["m4a", "flac"] = "m4a"
    album_title: str = Field(default="", max_length=120)
    track_number: int | None = Field(default=None, ge=1, le=20)
    title: str = Field(default="Untitled", max_length=120)
    style: str = Field(default="", max_length=2400)
    lyrics: str = Field(default="", max_length=12000)
    cot: Literal["full", "melody", "off"] = "full"
    seed: int = Field(default=831001, ge=0, le=2147483647)
    cfg_scale: float | None = Field(default=None, ge=0.5, le=2.0)
    max_tokens: int = Field(default=9000, ge=200, le=9000)
    abc: str = Field(default="", max_length=30000)
    auto_assist: bool = False
    brief: str = Field(default="", max_length=6000)
    language: LyricLanguage = "日本語"
    choices: MusicChoices = Field(default_factory=MusicChoices)
    assist_model: str = Field(default="", max_length=100)
    reference_track: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def score_mode(self):
        if self.engine == "stable-audio-3-medium":
            if self.derivation_mode != "none" or self.abc.strip() or self.cfg_scale is not None or self.ace_lm != "none":
                raise ValueError("Stable Audio 3では通常のインスト生成を選んでください。ABC・派生・ACE LMは使用しません")
            if self.choices.vocal in ("male", "female"):
                raise ValueError("Stable Audio 3はインスト専用です")
            self.choices = self.choices.model_copy(update={"vocal":"instrumental"})
            self.lyrics = "[Instrumental]"
            self.cot = "off"
        if self.duration_mode == "auto":
            if self.engine not in ("ace-xl-turbo", "stable-audio-3-medium") or self.derivation_mode == "cover":
                raise ValueError("曲長おまかせはACE-Step・Stable Audio 3の通常生成などで利用できます")
            self.auto_assist = True
        if bool(self.source_song_id) != (self.derivation_mode != "none"):
            raise ValueError("派生元の曲と参照方法を両方指定してください")
        if self.derivation_mode == "score" and (self.engine != "yue2" or self.cot == "off"):
            raise ValueError("譜面の派生にはYuE2のFull/Melodyを使用してください")
        if self.derivation_mode in ("cover", "timbre") and self.engine != "ace-xl-turbo":
            raise ValueError("音源の参照にはACE-Stepを使用してください")
        if self.derivation_mode == "cover" and self.ace_lm != "none":
            raise ValueError("構成を保つ派生では元音源を計画として使うためLMを無効にしてください")
        if self.engine == "ace-xl-turbo":
            if self.abc.strip() or self.cfg_scale is not None:
                raise ValueError("ACE-Step XL TurboではABC譜面・CFGは使えません")
            if len(self.lyrics) > 4096:
                raise ValueError("ACE-Stepの歌詞は4096文字以内にしてください")
        if not self.auto_assist and self.choices.vocal != "instrumental":
            if len(self.style.strip()) < 3 or not self.lyrics.strip():
                raise ValueError("スタイルと歌詞を入力するか、Codexの自動支援を有効にしてください")
        if self.abc.strip() and self.cot == "off":
            raise ValueError("ABC譜面を使う場合は full または melody を選んでください")
        return self


class AssistInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    engine: Literal["yue2", "ace-xl-turbo", "stable-audio-3-medium"] = "yue2"
    duration: int = Field(default=60, ge=10, le=180)
    duration_mode: Literal["fixed", "auto"] = "fixed"
    brief: str = Field(min_length=3, max_length=6000)
    language: LyricLanguage = "日本語"
    recent_titles: list[str] = Field(default_factory=list, max_length=200)
    current_style: str = Field(default="", max_length=2400)
    current_lyrics: str = Field(default="", max_length=12000)
    preserve_lyrics: bool = True
    model: str = Field(default="", max_length=100)
    choices: MusicChoices = Field(default_factory=MusicChoices)
    current_abc: str = Field(default="", max_length=30000)
    reference_track: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def instrumental_engine(self):
        if self.engine == "stable-audio-3-medium":
            self.choices = self.choices.model_copy(update={"vocal":"instrumental"})
            self.current_lyrics = ""
            self.current_abc = ""
            self.preserve_lyrics = False
        return self


class AssistResult(BaseModel):
    duration_reason: str = Field(default="", max_length=1500)
    bpm: int | None = Field(default=None, ge=40, le=220)
    model_config = ConfigDict(extra="forbid")
    title: str = Field(max_length=120)
    style: str = Field(min_length=3, max_length=2400)
    lyrics: str = Field(min_length=1, max_length=12000)
    duration: int = Field(default=60, ge=10, le=180)
    explanation: str = Field(max_length=6000)
    tips: list[str] = Field(max_length=8)
    melody_plan: str = Field(default="", max_length=3000)
    reference_analysis: str = Field(default="", max_length=3000)
    originality_note: str = Field(default="", max_length=1500)


ASSIST_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {**{k: {"type": "string"} for k in ["title", "style", "lyrics", "explanation", "melody_plan", "reference_analysis", "originality_note"]},
                   "tips": {"type": "array", "items": {"type": "string"}}},
    "required": ["title", "style", "lyrics", "explanation", "tips", "melody_plan", "reference_analysis", "originality_note"],
}

ASSIST_SCHEMA["properties"]["lyrics"]["minLength"] = 1
ASSIST_SCHEMA["properties"]["title"]["minLength"] = 1
ASSIST_SCHEMA["properties"]["style"]["minLength"] = 3

ASSIST_SCHEMA["properties"]["duration"] = {"type":"integer","minimum":10,"maximum":180}
ASSIST_SCHEMA["required"].append("duration")

ASSIST_SCHEMA["properties"]["bpm"] = {"anyOf":[{"type":"integer","minimum":40,"maximum":220},{"type":"null"}]}
ASSIST_SCHEMA["required"].append("bpm")

ASSIST_SCHEMA["properties"]["duration_reason"] = {"type":"string"}
ASSIST_SCHEMA["required"].append("duration_reason")
