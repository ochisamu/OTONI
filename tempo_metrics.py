"""Tempo estimates from detected beats; do not round individual short intervals."""
import numpy as np


def summarize_beats(beats, duration, target):
    beats=np.asarray(beats,dtype=float)
    if np.any(~np.isfinite(beats)) or np.any(np.diff(beats)<=0):
        raise ValueError('Beat timestamps must be finite and strictly increasing')
    span=min(8,max(1,len(beats)-1))
    tempos=60*span/(beats[span:]-beats[:-span]) if len(beats)>1 else np.array([])
    centers=(beats[span:]+beats[:-span])/2 if len(beats)>1 else np.array([])
    median=float(np.median(tempos)) if len(tempos) else None
    windows=[]
    for start in range(0,int(duration),15):
        local=tempos[(centers>=start)&(centers<start+15)]
        if len(local)>3:windows.append({'start':start,'bpm':round(float(np.median(local)),2)})
    window_values=[w['bpm'] for w in windows]
    unstable=(len(window_values)>1 and max(window_values)/min(window_values)>1.12)
    return {'estimated_bpm':round(median,2) if median else None,
     'unstable_estimate':unstable,
     'stability_note':'区間差が大きい：テンポ変化または拍の誤検出。代表BPMだけで判断しないでください。' if unstable else '区間ごとの推定も確認してください。',
     'relative_error_percent':round(100*abs(median-target)/target,2) if median else None,
     'half_double_candidates':[round(median/2,2),round(median*2,2)] if median else [],
     'windows':windows,'tempo_estimator':f'median over {span}-beat spans',
     'measurement_note':'8拍区間を使って検出時刻の量子化誤差を抑制。半速/倍速・誤検出・自由テンポの曖昧さは残ります。'}
