"""Serialize studio and experiment workers on the local GPU."""
from contextlib import contextmanager
from pathlib import Path
import fcntl

@contextmanager
def gpu_lock():
    path = Path(__file__).resolve().parent/'work/gpu.lock'
    path.parent.mkdir(exist_ok=True)
    with path.open('a') as f:
        print('STATUS GPUの利用順を待っています', flush=True)
        fcntl.flock(f, fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(f, fcntl.LOCK_UN)
