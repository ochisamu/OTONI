"""Bounded tempo edits for YuE2's generated ABC; audio tempo remains to be verified."""
import re


def set_score_bpm(abc: str, bpm: int) -> str:
    if not 40 <= bpm <= 220:
        raise ValueError('BPM outside supported range')
    # Only handle the documented simple global tempo header. Do not silently flatten
    # inline tempo changes or a score without an unambiguous tempo header.
    headers = re.findall(r'^Q:[^\r\n]*', abc, re.M)
    if len(headers) != 1 or re.search(r'\[Q:', abc):
        raise ValueError('譜面に複数のテンポ指定、またはQヘッダーの欠落があります。BPMを安全に固定できません。')
    return re.sub(r'^Q:[^\r\n]*', f'Q:1/4={bpm}', abc, count=1, flags=re.M)


def score_bpm(abc: str):
    values = re.findall(r'^Q:\s*1/4\s*=\s*(\d+)\s*$', abc, re.M)
    return int(values[0]) if len(values) == 1 and not re.search(r'\[Q:', abc) else None
