"""Shared language choices for planning, drafting and model conditioning."""
from typing import Literal

LyricLanguage = Literal["日本語", "日本語＋英語フレーズ", "English", "中文"]
VOCAL_LANGUAGE_CODES = {"日本語": "ja", "日本語＋英語フレーズ": "ja", "English": "en", "中文": "zh"}
STYLE_LANGUAGE_TAGS = {"日本語": "Japanese", "日本語＋英語フレーズ": "mostly Japanese vocals with short English hooks", "English": "English", "中文": "Mandarin Chinese"}

LANGUAGE_INSTRUCTIONS = """
Language policy for both song drafts and album planning:
The language field specifies the sung language, not the title language. Unless the user explicitly
specifies a title language, choose an original Japanese, English or mixed title to fit the song;
never mechanically translate every title into the lyrics language. Preserve user-specified titles.
For language=日本語＋英語フレーズ, keep the story and most sung lines in natural Japanese, with
one or a few short original English phrases at musically meaningful moments, such as a chorus
hook or a response. Do not translate each Japanese line, alternate languages mechanically, or
turn the whole song into English. Make the English idiomatic, singable and connected to the theme.
Describe this bilingual vocal delivery in the English style prompt. In album plans, carry this
intent into vocal track briefs, varying phrase placement and title languages naturally across
tracks without forcing every title or chorus into the same pattern.
For other language choices, use that language as requested; follow explicit user preferences
about language mixing. Preserve existing lyrics EXACTLY when preserve_lyrics is true, even if
that means adding no English. Instrumental tracks must remain wordless regardless of language.
English structural tags such as [Chorus] are metadata, not bilingual sung phrases.
Keep explanatory text Japanese and style/cover prompts English as otherwise instructed.
"""
