# DiffSynth Music / MuLaCover

These integrations use separate environments and the existing single-GPU queue. The earlier environment-consolidation proposal remains on hold.

## Setup

After the shared setup, run from the checkout directory:

```bash
./scripts/setup_diffsynth.sh
./scripts/setup_mulacover.sh
```

These scripts download pinned official source and model assets. DiffSynth Music weights are approximately 34GB; MuLaCover, its codec, style encoder and audio transcriber require approximately 16GB, plus Python environments and caches. Model code shipped with the fixed DiffSynth checkpoint is loaded by its official template pipeline. Check the upstream terms before use.

DiffSynth Music uses PyTorch 2.10 / CUDA 12.8 and Python 3.12. MuLaCover uses Python 3.10 and PyTorch 2.10 / CUDA 12.8 on this installation; the upstream example uses CUDA 13.0. This difference is deliberate for the existing GPU environment, and compatibility must be checked on other machines. The MuLa environment pins PyArrow 20 to preserve compatibility with its upstream dataset dependency.

## Using the models

DiffSynth Music is available for single tracks and original albums, including mixed-model albums. Choose native generation or beat conditioning without a source track. For vocals, accompaniment, prosody or timbre conditioning, select a completed track from your library. Beat mode conditions on a click at the specified BPM; it does not mix that click into the saved audio.

MuLaCover is available for single-track covers. Choose a completed source track, or select “MuLaCoverでカバーを作る” in a track's menu. It transcribes source audio to symbolic melody/chords, then generates a new interpretation using lyrics and style. The duration setting is a generation upper limit. MuLaCover is excluded from automatic album planning because it requires a source recording.

Codex assistance uses the model-specific guidance in CONTROL_PROMPT_GUIDE.md. MuLaCover style uses named fields (`topic`, `genre`, `instrument`, `mood`); lyrics remain a separate multiline field. Existing user lyrics are preserved when requested. No exact preservation of melody, voice, lyrics or BPM is guaranteed.

The source recording is snapshotted into the new job, so changing or deleting the original does not break an already queued job. DiffSynth conditioning uses up to the selected duration of the reference. This first integration accepts library audio only; uploading external audio or MIDI is not implemented. MuLaCover's generated symbolic MIDI is retained in the job's `symbolic/` directory for inspection on the server.

## Terms

OTONI remains an MIT-licensed assistance tool. Read the model-specific terms:

- DiffSynth Music: https://huggingface.co/DiffSynth-Studio/DiffSynth-Music
- MuLaCover: https://github.com/HeartMuLa/MuLaCover/blob/main/MODEL_LICENSE

The MuLaCover release explicitly restricts its weights and generated outputs to noncommercial use; its Apache-2.0 source license does not override that. OTONI displays a notice when the model is selected.

## 日本語の操作案内

- DiffSynth Music：通常・ビート制御は元曲不要。歌声／伴奏／抑揚／音色の制御はライブラリから完成曲を選択。
- MuLaCover：「元曲からカバー」を作るモデル。生成済みの曲メニューからも開始できます。長さは上限です。
- Codexの提案・自動支援、M4A/FLAC保存、共通プレイヤーに対応。GPUは従来どおり順次処理します。
- MuLaCoverの重み・生成物は公式の非商用条件を確認してください。MIDIアップロードや外部音源アップロードは今回のUIには含みません。

## Validation on RTX 5060 Ti 16GB

2026-09-16: a 15.04-second native DiffSynth instrumental completed in 21.33 seconds (PyTorch peak 7.84 GiB). A MuLaCover test from an existing OTONI recording produced 14.96 seconds in 56.27 seconds (peak 13.71 GiB). Through the application queue, a 15.04-second DiffSynth beat-conditioned track at requested 112 BPM completed in 90.78 seconds (peak 8.87 GiB), followed by a 14.96-second MuLaCover track in 48.85 seconds (peak 13.71 GiB). Both were saved as M4A in the library. These are single short functional tests, not quality or BPM-accuracy benchmarks, and do not validate every duration or control mode.

DiffSynth's small `placeholder_audio` root parameter is explicitly placed on CUDA because the pinned upstream DiT concatenates it directly with CUDA inputs; its large layers retain official CPU offload. Template modes use a lower model VRAM budget and lazy template loading. MuLaCover reference input is decoded from M4A/FLAC to temporary PCM and trimmed to the requested generation budget before symbolic transcription; temporary PCM is removed afterward. The original reference snapshot is retained.
