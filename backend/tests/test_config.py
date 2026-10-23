"""JWT signing-key handling."""
from __future__ import annotations

from app.core.config import Settings


def test_missing_secret_is_generated_and_persisted(tmp_path):
    first = Settings(secret_key="", data_dir=tmp_path)
    first.ensure_secret_key()
    assert len(first.secret_key) >= 40
    assert (tmp_path / ".secret_key").read_text(encoding="utf-8").strip() == first.secret_key

    restarted = Settings(secret_key="", data_dir=tmp_path)
    restarted.ensure_secret_key()
    assert restarted.secret_key == first.secret_key      # tokens survive restarts


def test_old_placeholder_secrets_are_replaced(tmp_path):
    for i, placeholder in enumerate(["dev-secret-change-me", "change-me-to-a-long-random-string"]):
        data_dir = tmp_path / str(i)
        data_dir.mkdir()
        s = Settings(secret_key=placeholder, data_dir=data_dir)
        s.ensure_secret_key()
        assert s.secret_key != placeholder


def test_each_install_gets_its_own_key(tmp_path):
    keys = []
    for name in ("install-a", "install-b"):
        (tmp_path / name).mkdir()
        s = Settings(secret_key="", data_dir=tmp_path / name)
        s.ensure_secret_key()
        keys.append(s.secret_key)
    assert keys[0] != keys[1]


def test_explicit_secret_is_kept(tmp_path):
    s = Settings(secret_key="an-operator-provided-production-secret", data_dir=tmp_path)
    s.ensure_secret_key()
    assert s.secret_key == "an-operator-provided-production-secret"
    assert not (tmp_path / ".secret_key").exists()
