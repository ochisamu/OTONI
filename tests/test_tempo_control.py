import pytest
from tempo_control import set_score_bpm, score_bpm


def test_tempo_edit_preserves_notes_chords_and_meter():
    abc = 'X:1\nM:4/4\nL:1/8\nQ:1/4=110\nK:C\n"Cmaj7"C2E2 G4|\n'
    revised = set_score_bpm(abc, 78)
    assert revised.replace('Q:1/4=78', 'Q:1/4=110') == abc
    assert score_bpm(revised) == 78


@pytest.mark.parametrize('abc', ['X:1\nK:C\nC4|', 'Q:1/4=90\nQ:1/4=100\n', 'Q:1/4=90\nC4[Q:1/4=110]D4|'])
def test_ambiguous_tempo_is_not_silently_overwritten(abc):
    with pytest.raises(ValueError):
        set_score_bpm(abc, 100)


def test_ace_lm_is_explicit_and_defaults_to_off():
    from schemas import SongInput
    base={'engine':'ace-xl-turbo','style':'jazz house','lyrics':'[Instrumental]',
          'choices':{'vocal':'instrumental'}}
    assert SongInput(**base).ace_lm == 'none'
    assert SongInput(**base,ace_lm='1.7B').ace_lm == '1.7B'
    with pytest.raises(ValueError): SongInput(**base,ace_lm='missing')


def test_tempo_measurement_avoids_short_interval_quantization():
    import numpy as np
    from tempo_metrics import summarize_beats
    beats=np.round(np.arange(120)*60/124/.02)*.02
    result=summarize_beats(beats,60,124)
    assert abs(result['estimated_bpm']-124)<.4
    assert result['windows']
    assert summarize_beats([],60,124)['estimated_bpm'] is None
    with pytest.raises(ValueError):summarize_beats([1,1],60,124)
