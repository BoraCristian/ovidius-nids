"""The one-click launcher (run.py).

Run in a subprocess: importing run.py installs signal handlers and an atexit
hook, which must not leak into the pytest process.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_snippet(code: str, **env_overrides: str) -> subprocess.CompletedProcess:
    env = {**os.environ, **env_overrides}
    return subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env,
                          capture_output=True, timeout=60)


def test_servers_listen_on_localhost_only():
    proc = run_snippet(
        "import json, run; print(json.dumps([run.backend_command(), run.frontend_command('npm')]))"
    )
    assert proc.returncode == 0, proc.stderr
    backend_cmd, frontend_cmd = json.loads(proc.stdout.decode("utf-8").splitlines()[0])
    assert backend_cmd[backend_cmd.index("--host") + 1] == "127.0.0.1"
    assert "--host" not in frontend_cmd


def test_status_symbols_survive_a_non_utf8_redirect():
    """Redirected output on Windows defaults to cp1252, which can't encode ▸ / ✓."""
    proc = run_snippet("import run; run.step('starting'); run.ok('done')",
                       PYTHONIOENCODING="cp1252")
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    out = proc.stdout.decode("utf-8")
    assert "▸ starting" in out and "✓ done" in out
