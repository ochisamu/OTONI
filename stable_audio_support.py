"""Stable Audio 3 Medium integration metadata and text-only conditioning."""
ENGINE='stable-audio-3-medium'
MODEL='stabilityai/stable-audio-3-medium'
GUIDE='https://kb.stability.ai/knowledge-base/stable-audio-3-prompt-guide'

def music_prompt(request):
    # Lyrics and YuE/ACE section tags are not Stable Audio conditioning fields.
    parts=['Instrumental music. No vocals, singing, humming or speech.',request.style.strip()]
    if request.choices.bpm is not None:parts.append(f'Tempo: {request.choices.bpm} BPM.')
    return ' '.join(parts)
