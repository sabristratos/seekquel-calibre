import time
from pathlib import Path

from calibre.constants import config_dir

LOG_NAME = 'seekquel-sync.log'
MAX_BYTES = 512 * 1024
KEEP_BYTES = 128 * 1024


def log_path():
    return Path(config_dir) / 'plugins' / LOG_NAME


def note(message):
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")}  {message}\n'

    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists() and path.stat().st_size > MAX_BYTES:
            _trim(path)

        with path.open('a', encoding='utf-8') as handle:
            handle.write(line)
    except Exception:
        pass


def read_log():
    try:
        return log_path().read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''
    except Exception as error:
        return f'Could not read the log: {error}'


def clear_log():
    try:
        log_path().unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _trim(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    kept = text[-KEEP_BYTES:]
    start = kept.find('\n')

    if start != -1:
        kept = kept[start + 1:]

    path.write_text(kept, encoding='utf-8')
