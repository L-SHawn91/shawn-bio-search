import os

def _load_simple_env_file(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key and key not in os.environ:
                    os.environ[key] = value.strip()
        return True
    except FileNotFoundError:
        return False


def load_openclaw_shared_env() -> None:
    candidates = [
        os.environ.get("OPENCLAW_SHARED_ENV"),
        "/home/mdge/.openclaw/workspace/.secrets/shared/api_keys.env",
        os.path.expanduser("~/.openclaw/workspace/.secrets/shared/api_keys.env"),
    ]
    for path in candidates:
        if path and _load_simple_env_file(path):
            os.environ.setdefault("OPENCLAW_SHARED_ENV_LOADED", path)
            break

    service_candidates = [
        os.environ.get("OPENCLAW_SHARED_SERVICES"),
        "/home/mdge/.openclaw/workspace/.secrets/shared/services.env",
        os.path.expanduser("~/.openclaw/workspace/.secrets/shared/services.env"),
    ]
    for path in service_candidates:
        if path and _load_simple_env_file(path):
            os.environ.setdefault("OPENCLAW_SHARED_SERVICES_LOADED", path)
            break
