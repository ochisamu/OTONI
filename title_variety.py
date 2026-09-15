"""History-aware title context and normalized duplicate detection."""
import re
import unicodedata
from difflib import SequenceMatcher


def title_key(title):
    return re.sub(r'[\W_]+', '', unicodedata.normalize('NFKC', title).casefold())


def similar_title(title, others):
    key = title_key(title)
    return any(key == title_key(t) or (min(len(key), len(title_key(t))) >= 5 and
        SequenceMatcher(None, key, title_key(t)).ratio() > .86) for t in others)

TITLE_INSTRUCTIONS = '''\nTitle diversity: recent_titles lists existing library titles. Invent a specific title
without changing the requested musical identity or forcing a new story onto the song.
Title novelty is secondary to the user's intended sound and lyrical mood. Common words are
acceptable when appropriate; avoid repetitive combinations, not the user's requested atmosphere.
Draw on the song's own imagery or phrasing rather than imposing unrelated subject matter.
Avoid repeating their distinctive nouns or syntax. Do not default to Neon, Night, Dawn,
Afterglow, 雨上がり, 夜明け, 余白, 桟橋, 光, or noun + の + noun repeatedly. Mix naming forms:
a short spoken phrase, an unusual tangible detail, a verb, a fictional place, a number
with context. Do not append serial numbers to an existing title. Check recent_titles
before returning. Keep the title meaningful to this particular composition.\n'''
