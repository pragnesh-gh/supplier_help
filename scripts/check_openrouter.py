"""Read-only setup checks. No inference; never prints or writes a credential.

Run --catalog without a key. Run --key to check an existing process/.env key.
Only HTTPS requests to OpenRouter's fixed API origin are allowed.
"""
import argparse
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def local_config():
    values = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, value = stripped.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    values.update(os.environ)
    return values


def request(path, key=None):
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request("https://openrouter.ai/api/v1/" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", action="store_true", help="Check public model metadata")
    parser.add_argument("--key", action="store_true", help="Check existing key without inference")
    args = parser.parse_args()
    env = local_config()
    model = env.get("OPENROUTER_MODEL") or json.loads((ROOT / "config/models.json").read_text())["language_model"]["model"]
    print(f"Selected model: {model}")
    print("Prototype: offline; live inference is disabled")
    print("Credential present: " + ("yes" if env.get("OPENROUTER_API_KEY") else "no"))
    try:
        if args.catalog:
            entry = next((m for m in request("models")["data"] if m["id"] == model), None)
            if entry is None:
                print("Model absent from current catalog; no substitute selected")
                return 1
            print(json.dumps({k: entry.get(k) for k in ("id", "context_length", "architecture", "supported_parameters")}, indent=2))
        if args.key:
            key = env.get("OPENROUTER_API_KEY")
            if not key:
                print("Key check skipped: set OPENROUTER_API_KEY or put it in ignored .env")
                return 2
            request("key", key)
            print("OpenRouter accepted the key. Model/provider access is not yet tested.")
    except urllib.error.HTTPError as error:
        print(f"OpenRouter check failed with HTTP {error.code}; no response body logged")
        return 1
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        print("OpenRouter metadata request failed; verify connection and configuration")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
