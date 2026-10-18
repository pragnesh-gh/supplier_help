"""Server-side environment: an optional env file merged with os.environ (os.environ wins)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_environment(env_file=None):
    values = {}
    path = Path(env_file) if env_file else ROOT / '.env'
    if path.is_file():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip().strip('"\'')
    values.update(os.environ)
    return values
