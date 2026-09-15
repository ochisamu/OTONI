"""Validate compressed audio before removing redundant generated audio files."""
import json
import subprocess
from pathlib import Path

FORMATS = {'m4a': ('audio.m4a', ['-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart']),
           'flac': ('audio.flac', ['-c:a', 'flac'])}


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    stream = next(s for s in data['streams'] if s['codec_type'] == 'audio')
    return float(data['format']['duration']), int(stream['sample_rate']), int(stream['channels'])


def stored_audio(folder):
    for name in ('audio.m4a', 'audio.flac', 'song.wav', 'artifacts/audio.flac'):
        if (folder / name).is_file():
            return name
    return None


def finalize_audio(folder: Path, format='m4a', title='', album='', track=None):
    """Atomically encode and decode-check the destination before deleting originals."""
    name, codec = FORMATS[format]
    dest = folder / name
    source = next((p for p in [folder/'song.wav', folder/'artifacts/audio.flac',
                  folder/'audio.flac', folder/'audio.m4a'] if p.is_file()), None)
    if source is None:
        raise RuntimeError('圧縮する音声がありません')
    before = sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
    if source != dest:
        tmp = folder / ('encoding.' + format)
        try:
            args = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(source), '-map', '0:a:0',
                    *codec, '-metadata', f'title={title}']
            if album: args += ['-metadata', f'album={album}']
            if track: args += ['-metadata', f'track={track}']
            subprocess.run([*args, str(tmp)], check=True, capture_output=True)
            original, sr, channels = probe(source)
            duration, out_sr, out_channels = probe(tmp)
            if abs(duration-original) > .15 or out_sr != sr or out_channels != channels:
                raise RuntimeError('音声の長さ・チャンネル数が一致しません。元音声を保持しました')
            subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(tmp), '-f', 'null', '-'],
                           check=True, capture_output=True)
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
    else:
        probe(dest)
    # Only generated, redundant audio. Keep scores, inputs, seeds and result metadata.
    for p in [folder/'song.wav', folder/'artifacts/audio.flac', folder/'audio.flac', folder/'audio.m4a',
              *list((folder/'ace-output').glob('*.flac')), *list((folder/'ace-output').glob('*.wav'))]:
        if p != dest: p.unlink(missing_ok=True)
    duration, sr, channels = probe(dest)
    after = sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
    result = {'format': format, 'file': name, 'bytes': dest.stat().st_size,
              'saved_bytes': max(0, before-after), 'audio_seconds': duration,
              'sample_rate': sr, 'channels': channels}
    tmp = folder/'storage.tmp'
    tmp.write_text(json.dumps(result, indent=2)); tmp.replace(folder/'storage.json')
    return result
