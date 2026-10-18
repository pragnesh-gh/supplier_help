"""Server-side environment: env files merged with os.environ (os.environ wins).

With ``--env-file`` only that file is read. Without it, the root ``.env`` is read first and
then ``research_agent/.env`` (where the research keys usually live), so the app runs live by
default. A key in the root file wins over the same key in research_agent/.env. Values are
never printed or logged.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILES = (ROOT / '.env', ROOT / 'research_agent' / '.env')


def _read_file(path):
    values = {}
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                if key.startswith('export '):
                    key = key[len('export '):].strip()
                values[key] = value.strip().strip('"\'')
    return values


def read_environment(env_file=None):
    files = [Path(env_file)] if env_file else list(DEFAULT_ENV_FILES)
    values = {}
    for path in reversed(files):  # earlier files win
        values.update({k: v for k, v in _read_file(path).items() if v != '' or k not in values})
    values.update(os.environ)
    return values
