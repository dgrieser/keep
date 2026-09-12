"""Configuration and cache file handling.

The config file stores the account email and the Google master token. It is written with
owner-only permissions (0600). The state cache holds a serialized snapshot of the Keep
database so that subsequent commands only need an incremental sync.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ENV_EMAIL = "KEEP_EMAIL"
ENV_MASTER_TOKEN = "KEEP_MASTER_TOKEN"
ENV_CONFIG_DIR = "KEEP_CONFIG_DIR"
ENV_CACHE_DIR = "KEEP_CACHE_DIR"


def config_dir() -> Path:
    if override := os.environ.get(ENV_CONFIG_DIR):
        return Path(override)
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "keep"


def cache_dir() -> Path:
    if override := os.environ.get(ENV_CACHE_DIR):
        return Path(override)
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "keep"


def config_path() -> Path:
    return config_dir() / "config.json"


def state_path() -> Path:
    return cache_dir() / "state.json"


@dataclass
class Config:
    email: str
    master_token: str
    device_id: str | None = None

    def to_dict(self) -> dict:
        data = {"email": self.email, "master_token": self.master_token}
        if self.device_id:
            data["device_id"] = self.device_id
        return data


class ConfigError(Exception):
    """Raised when no usable credentials can be found."""


def _write_private(path: Path, payload: str) -> None:
    """Atomically write ``payload`` to ``path`` with 0600 permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def load_config(path: Path | None = None) -> Config:
    """Load credentials from the environment first, then the config file."""
    env_email = os.environ.get(ENV_EMAIL)
    env_token = os.environ.get(ENV_MASTER_TOKEN)
    if env_email and env_token:
        return Config(email=env_email, master_token=env_token)

    path = path or config_path()
    if not path.exists():
        raise ConfigError(f"No credentials found at {path}. Run `keep login` first.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Could not read {path}: {exc}") from exc

    email = env_email or data.get("email")
    token = env_token or data.get("master_token")
    if not email or not token:
        raise ConfigError(f"{path} is missing 'email' or 'master_token'. Run `keep login`.")
    return Config(email=email, master_token=token, device_id=data.get("device_id"))


def save_config(cfg: Config, path: Path | None = None) -> Path:
    path = path or config_path()
    _write_private(path, json.dumps(cfg.to_dict(), indent=2) + "\n")
    return path


def delete_config(path: Path | None = None) -> bool:
    path = path or config_path()
    if path.exists():
        path.unlink()
        return True
    return False


def load_state(path: Path | None = None) -> dict | None:
    path = path or state_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_state(state: dict, path: Path | None = None) -> Path:
    path = path or state_path()
    _write_private(path, json.dumps(state))
    return path


def delete_state(path: Path | None = None) -> bool:
    path = path or state_path()
    if path.exists():
        path.unlink()
        return True
    return False
