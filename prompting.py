"""Application presets; official guidance is kept separately with provenance."""
from language_policy import STYLE_LANGUAGE_TAGS
from schemas import MusicChoices

GUIDE_REVISION = "88da114a67df892af0329472073b96a5ef700b93"
GUIDE_URL = "https://github.com/multimodal-art-projection/YuE/blob/" + GUIDE_REVISION + "/docs/generation.md"
GENRES = {
    "auto": "Contemporary pop, piano, rounded bass and restrained drums",
    "pop": "Contemporary pop, piano, electric bass, crisp drums and subtle synth pads",
    "citypop": "City pop, Rhodes electric piano, syncopated bass, clean rhythm guitar and tight drums",
    "rock": "Alternative rock, expressive electric guitars, electric bass and dynamic live drums",
    "acoustic": "Acoustic folk pop, fingerpicked acoustic guitar, upright bass and brushed percussion",
    "jazz": "Jazz, warm piano, upright bass, brushed drums and lyrical tenor saxophone",
    "rnb": "Contemporary R&B, Rhodes chords, deep bass and relaxed syncopated drums",
    "lofi": "Lo-fi hip hop, mellow electric piano, rounded bass, dusty laid-back drums",
    "edm": "Melodic electronic dance music, arpeggiated synths, deep bass and four-on-the-floor drums",
    "ambient": "Ambient, evolving soft synthesizer textures, spacious piano and restrained percussion",
    "orchestral": "Cinematic orchestral music, expressive strings, warm woodwinds and restrained percussion",
    "metal": "Melodic metal, layered distorted guitars, driving bass and powerful live drums",
}
TEMPOS = {"auto": "natural flowing tempo", "slow": "slow relaxed tempo", "medium": "moderate steady tempo", "fast": "fast energetic tempo"}
VOICES = {"auto": "expressive lead vocal", "female": "warm expressive female lead vocal", "male": "warm expressive male lead vocal", "instrumental": "instrumental only, no singing, no spoken voice, instruments carry the lead melody"}
MOODS = {"auto": "emotionally coherent", "hopeful": "hopeful and uplifting", "sad": "bittersweet and wistful", "energetic": "energetic and joyful", "calm": "calm and intimate", "dark": "dark and atmospheric"}
MELODIES = {"balanced": "Coherent melodic phrases with repetition and gentle variation.", "catchy": "A memorable short melodic hook returns with small variations; restrained verses open into a clear, singable chorus with breathing space.", "lyrical": "Lyrical stepwise melodic motion, balanced phrases and natural pauses; a recurring motif develops into a gentle climax.", "dramatic": "A restrained opening develops through rising melodic contours toward a contrasting, emotionally resolved climax."}


def preset_style(choices: MusicChoices, language="日本語"):
    tempo = f"{choices.bpm} BPM" if choices.bpm is not None else TEMPOS[choices.tempo]
    language_tag = STYLE_LANGUAGE_TAGS[language]
    voice = VOICES[choices.vocal]
    if choices.vocal != "instrumental":
        voice = language_tag + ", " + voice
    return ". ".join([GENRES[choices.genre], tempo, voice, MOODS[choices.mood], MELODIES[choices.melody], "Clear natural production with space for the lead melody."])


def enforce_instrumental(style: str):
    # Never send sung words in instrumental mode. The request is soft conditioning,
    # not a guarantee that the model will never hallucinate a voice.
    prefix = "Instrumental only, no vocals, no singing, no speech. "
    return style if style.startswith(prefix) else prefix + style
