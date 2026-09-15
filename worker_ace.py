"""Isolated ACE-Step XL Turbo inference using its official Python API."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

from language_policy import VOCAL_LANGUAGE_CODES
from schemas import SongInput
from audio_storage import finalize_audio


def main():
    """Render one song and publish artifacts in the studio's shared job format."""
    root = Path(__file__).resolve().parent
    folder = Path(sys.argv[1]).resolve()
    request = SongInput.model_validate_json((folder / "input.json").read_text())
    if request.engine != "ace-xl-turbo":
        raise ValueError("Wrong worker for selected engine")
    checkpoints = root / "models/ace"
    os.environ["ACESTEP_CHECKPOINTS_DIR"] = str(checkpoints)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    import soundfile as sf
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    class LocalXLHandler(AceStepHandler):
        """Require the installed XL assets without downloading unused standard/LM weights."""

        def _ensure_models_present(self, *, checkpoint_path, config_path,
                                   prefer_source, vae_variant=None):
            if (checkpoint_path != checkpoints or config_path != "acestep-v15-xl-turbo"
                    or vae_variant != "official" or not (checkpoints / ".ready").is_file()):
                return "XL Turboのモデルをscripts/setup_ace.shで準備してください", False
            for name in ("acestep-v15-xl-turbo", "vae", "Qwen3-Embedding-0.6B"):
                if not any((checkpoints / name).glob("*.safetensors")):
                    return f"Missing model weights: {name}", False
            return None

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA対応GPUが見つかりません")
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    print("STATUS ACE-Step 1.5 XL Turboを読み込み中（BF16・CPU退避）", flush=True)
    handler = LocalXLHandler()
    message, ok = handler.initialize_service(
        project_root=str(root / "vendor/ACE-Step-1.5"), config_path="acestep-v15-xl-turbo",
        device="cuda", offload_to_cpu=True, offload_dit_to_cpu=True,
        use_flash_attention=False, compile_model=False, quantization=None,
        use_mlx_dit=False, vae_checkpoint="official")
    print(message, flush=True)
    if not ok:
        raise RuntimeError(message)
    instrumental = request.choices.vocal == "instrumental"
    lm = None
    if request.ace_lm == "1.7B":
        if not (checkpoints / "acestep-5Hz-lm-1.7B/.ready").is_file():
            raise RuntimeError("scripts/download_ace_lm.py で1.7B LMを準備してください")
        from acestep.llm_inference import LLMHandler
        print("STATUS 音楽専用1.7B LMを読み込み中", flush=True)
        lm = LLMHandler()
        message, ok = lm.initialize(checkpoint_dir=str(checkpoints),
            lm_model_path="acestep-5Hz-lm-1.7B", backend="pt", device="cuda",
            offload_to_cpu=True, dtype=torch.bfloat16)
        print(message, flush=True)
        if not ok: raise RuntimeError(message)
    bpm = request.choices.bpm or {"slow": 72, "medium": 104, "fast": 140}.get(request.choices.tempo)
    source_audio = None
    if request.derivation_mode in ("cover", "timbre"):
        lineage = json.loads((folder / "derivation.json").read_text())
        name = lineage.get("audio_file")
        if name not in ("source-audio.m4a", "source-audio.flac", "source-audio.wav"):
            raise RuntimeError("派生元音源の保存情報が不正です")
        source_audio = str(folder / name)
        if not Path(source_audio).is_file(): raise RuntimeError("派生元音源が見つかりません")
    params = GenerationParams(
        task_type="cover" if request.derivation_mode == "cover" else "text2music", caption=request.style,
        src_audio=source_audio if request.derivation_mode == "cover" else None,
        reference_audio=source_audio if request.derivation_mode == "timbre" else None,
        audio_cover_strength=request.reference_strength,
        lyrics="[Instrumental]" if instrumental else request.lyrics,
        instrumental=instrumental,
        vocal_language="unknown" if instrumental else VOCAL_LANGUAGE_CODES[request.language],
        duration=request.duration, bpm=bpm, seed=request.seed, inference_steps=8,
        thinking=lm is not None, use_cot_metas=False, use_cot_caption=False, use_cot_language=False,
    )
    config = GenerationConfig(batch_size=1, use_random_seed=False,
                              seeds=[request.seed], audio_format="flac")
    length_label = "元音源の長さで" if request.derivation_mode == "cover" else f"{request.duration}秒の"
    print(f"STATUS {length_label}{'インスト' if instrumental else '曲'}を生成中", flush=True)
    result = generate_music(handler, lm, params, config, save_dir=str(folder / "ace-output"))
    if not result.success or not result.audios:
        raise RuntimeError(result.error or result.status_message or "No audio returned")
    if lm is not None:
        codes = result.audios[0].get("params", {}).get("audio_codes", "")
        if not codes or "<|audio_code_" not in codes:
            raise RuntimeError("LMが音楽コードを生成していません。比較試験を中止します。")
        # Keep the actual LM result, not merely an enabled UI flag.
        (folder / "lm-result.json").write_text(json.dumps({
            "audio": {k:v for k,v in result.audios[0].items() if k != "tensor"},
            "metadata": result.extra_outputs.get("lm_metadata"),
        }, ensure_ascii=False, indent=2, default=str))
    source = Path(result.audios[0]["path"])
    audio, sample_rate = sf.read(source, always_2d=True)
    import numpy as np
    if not np.isfinite(audio).all() or np.max(np.abs(audio)) < 1e-5:
        raise RuntimeError("生成音声が無音または不正な値です")
    artifacts = folder / "artifacts"
    artifacts.mkdir(exist_ok=True)
    shutil.copy2(source, artifacts / "audio.flac")
    sf.write(folder / "song.wav", audio, sample_rate, subtype="PCM_24")
    summary = {
        "engine": request.engine, "model": "ACE-Step/acestep-v15-xl-turbo",
        "audio_seconds": len(audio) / sample_rate, "sample_rate": sample_rate,
        "truncated": {}, "elapsed_seconds": round(time.monotonic() - started, 2),
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "precision": "BF16", "cpu_offload": True, "thinking": lm is not None,
        "ace_lm": request.ace_lm, "inference_steps": 8,
        "lm_audio_code_count": codes.count("<|audio_code_") if lm is not None else 0,
        "derivation": {"source_song_id":request.source_song_id,"mode":request.derivation_mode,
                       "strength":request.reference_strength},
    }
    (artifacts / "result.json").write_text(json.dumps({"summary": summary, "params": params.to_dict(),
        "config": config.to_dict(), "source_versions": json.loads((root / "ace.lock.json").read_text())},
        ensure_ascii=False, indent=2))
    (folder / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    finalize_audio(folder, request.output_format, request.title, request.album_title, request.track_number)
    print("STATUS 完了", flush=True)


if __name__ == "__main__":
    from gpu_lock import gpu_lock
    with gpu_lock(): main()
