import json
import os
import stat

import pytest

from keep_cli import auth, client, config


def test_save_and_load_config_private(tmp_path):
    cfg = config.Config(email="a@b.c", master_token="aas_et/secret", device_id="abcd")
    path = config.save_config(cfg)
    assert path == config.config_path()
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600
    loaded = config.load_config()
    assert loaded == cfg


def test_env_override(monkeypatch):
    monkeypatch.setenv("KEEP_EMAIL", "env@example.com")
    monkeypatch.setenv("KEEP_MASTER_TOKEN", "env-token")
    cfg = config.load_config()
    assert cfg.email == "env@example.com" and cfg.master_token == "env-token"


def test_missing_config_message():
    with pytest.raises(config.ConfigError, match="keep login"):
        config.load_config()


def test_state_roundtrip():
    assert config.load_state() is None
    config.save_state({"a": 1})
    assert config.load_state() == {"a": 1}
    assert stat.S_IMODE(os.stat(config.state_path()).st_mode) == 0o600
    assert config.delete_state() is True


def test_open_keep_without_config_exits(run):
    result = run("list")
    assert result.exit_code == 1
    assert "keep login" in result.output


def test_login_exchanges_token(run, monkeypatch):
    calls = {}

    def fake_exchange(email, token, android_id):
        calls["args"] = (email, token, android_id)
        return {"Token": "aas_et/MASTER"}

    monkeypatch.setattr(auth.gpsoauth, "exchange_token", fake_exchange)
    monkeypatch.setattr(client, "verify_credentials", lambda cfg: calls.setdefault("verified", cfg))

    result = run("login", "--email", "me@example.com", input="oauth2_4/abc\n")
    assert result.exit_code == 0, result.output
    assert "Logged in as me@example.com" in result.output
    assert calls["args"][:2] == ("me@example.com", "oauth2_4/abc")
    assert len(calls["args"][2]) == 16
    data = json.loads(config.config_path().read_text())
    assert data["master_token"] == "aas_et/MASTER"
    assert data["device_id"] == calls["args"][2]
    assert calls["verified"].master_token == "aas_et/MASTER"


def test_login_exchange_failure(run, monkeypatch):
    monkeypatch.setattr(auth.gpsoauth, "exchange_token", lambda *a: {"Error": "BadAuthentication"})
    result = run("login", "--email", "me@example.com", "--oauth-token", "bad")
    assert result.exit_code == 1
    assert "BadAuthentication" in result.output
    assert not config.config_path().exists()


def test_login_with_master_token(run, monkeypatch):
    monkeypatch.setattr(client, "verify_credentials", lambda cfg: None)
    result = run("login", "--email", "me@example.com", "--master-token", "aas_et/X")
    assert result.exit_code == 0
    assert config.load_config().master_token == "aas_et/X"


def test_logout(run, monkeypatch):
    config.save_config(config.Config(email="x@y.z", master_token="t"))
    config.save_state({"nodes": []})
    result = run("logout")
    assert result.exit_code == 0
    assert not config.config_path().exists()
    assert not config.state_path().exists()
    assert "No stored credentials" in run("logout").output
