"""One isolated GPU process per song; exit returns all GPU memory."""
import json
import sys
import time
from pathlib import Path
from schemas import SongInput
from audio_storage import finalize_audio
from tempo_control import set_score_bpm, score_bpm


def main():
    folder = Path(sys.argv[1]).resolve()
    request = SongInput.model_validate_json((folder / "input.json").read_text())
    import torch
    from yue2 import YuE2Pipeline
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA対応GPUが見つかりません")
    root = Path(__file__).resolve().parent
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    print("STATUS モデルを読み込み中", flush=True)
    pipe = YuE2Pipeline.from_pretrained(
        str(root / "models/YuE2-3B"), vae=str(root / "models/YuE2-Vae"),
        device="cuda", backend="torch", memory_budget_gib=16,
        vae_core_frames=512, offload_ar=True, local_files_only=True)
    try:
        abc = request.abc.strip() or None
        tempo_mode = "provided_score" if abc else "text_guidance"
        if request.choices.bpm is not None and request.cot != "off" and abc is None:
            print("STATUS 譜面を計画し、指定BPMを反映中", flush=True)
            plan = pipe.plan(style=request.style, lyrics=request.lyrics,
                             cot=request.cot, seed=request.seed, cfg_scale=request.cfg_scale)
            if plan.truncated:
                raise RuntimeError("テンポ反映前の譜面が打ち切られました。歌詞・構成を短くしてください。")
            (folder / "planned-score.abc").write_text(plan.abc)
            abc = set_score_bpm(plan.abc, request.choices.bpm)
            (folder / "tempo-score.abc").write_text(abc)
            tempo_mode = "generated_score_tempo"
        song = pipe(style=request.style, lyrics=request.lyrics,
                    cot=request.cot, seed=request.seed, cfg_scale=request.cfg_scale,
                    abc=abc,
                    semantic_sampling={"max_tokens": request.max_tokens})
        print("STATUS 音声と生成条件を保存中", flush=True)
        result = song.save_artifacts(folder / "artifacts")
        song.save(folder / "song.wav")
        summary = {"audio_seconds": result["audio_seconds"], "sample_rate": result["sample_rate"],
                   "truncated": result["truncated"], "timing": song.timing,
                   "elapsed_seconds": round(time.monotonic() - started, 2),
                   "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                   "tempo": {"requested_bpm": request.choices.bpm, "mode": tempo_mode,
                             "score_bpm": score_bpm((folder / "artifacts/score.abc").read_text())
                                 if (folder / "artifacts/score.abc").exists() else None,
                             "audio_bpm_verified": False}}
        (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        finalize_audio(folder, request.output_format, request.title, request.album_title, request.track_number)
        print("STATUS 完了", flush=True)
    finally:
        pipe.close()


if __name__ == "__main__":
    from gpu_lock import gpu_lock
    with gpu_lock(): main()
