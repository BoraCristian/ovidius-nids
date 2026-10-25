"""
Ovidius NIDS — one-click launcher.

Run from VS Code (F5) or a terminal:

    python run.py

What it does (in order):
  1. Creates backend/.venv if missing.
  2. Installs backend requirements (requirements.txt) inside that venv.
  3. Installs frontend node_modules if missing.
  4. Starts the FastAPI backend on http://localhost:8000 (this machine only)
  5. Starts the Vite frontend on http://localhost:5173 (this machine only)
  6. Opens http://localhost:5173 in your default browser.
  7. Streams both processes' logs with [backend]/[frontend] prefixes.
  8. Ctrl+C cleanly stops everything.

Works on Windows, macOS, and Linux. Requires only:
  - Python 3.10+
  - Node.js 18+ and npm on PATH
"""
from __future__ import annotations

import argparse
import atexit
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths                                                                        #
# --------------------------------------------------------------------------- #
ROOT          = Path(__file__).resolve().parent
BACKEND_DIR   = ROOT / "backend"
FRONTEND_DIR  = ROOT / "frontend"
VENV_DIR      = BACKEND_DIR / ".venv"
REQUIREMENTS  = BACKEND_DIR / "requirements.txt"
ENV_EXAMPLE   = BACKEND_DIR / ".env.example"
ENV_FILE      = BACKEND_DIR / ".env"

BACKEND_HOST  = "127.0.0.1"
BACKEND_PORT  = 8000
FRONTEND_PORT = 5173
FRONTEND_URL  = f"http://localhost:{FRONTEND_PORT}"

IS_WINDOWS = platform.system() == "Windows"

# --------------------------------------------------------------------------- #
# Tiny terminal helpers                                                        #
# --------------------------------------------------------------------------- #
def _force_utf8_output() -> None:
    """Print ▸ / ✓ safely even when stdout is a file or pipe.

    Redirected output on Windows defaults to the ANSI code page (cp1252),
    which cannot encode those symbols and would crash the launcher.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


_force_utf8_output()


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


USE_COLOR = _supports_color()


def c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if USE_COLOR else s


def step(msg: str) -> None:
    print(c("36;1", f"▸ {msg}"), flush=True)


def ok(msg: str) -> None:
    print(c("32;1", f"✓ {msg}"), flush=True)


def warn(msg: str) -> None:
    print(c("33;1", f"! {msg}"), flush=True)


def fail(msg: str) -> None:
    print(c("31;1", f"✗ {msg}"), flush=True)


def banner() -> None:
    bar = "═" * 62
    print(c("36;1", bar))
    print(c("36;1", "   Ovidius NIDS — SIEM launcher"))
    print(c("36;1", "   Bachelor's Thesis — FMI, Universitatea Ovidius"))
    print(c("36;1", bar))


# --------------------------------------------------------------------------- #
# Python version sanity check                                                  #
# --------------------------------------------------------------------------- #
def check_python_version() -> None:
    """
    Scientific packages (scikit-learn, numpy) only ship Windows wheels
    for Python versions they've explicitly tested against.  If the user is on a
    brand-new Python (e.g. 3.15 the week it drops), pip will try to *compile*
    those packages from C/C++/Fortran source, which needs MSVC build tools and
    will fail with a confusing meson error.

    We refuse to run on anything newer than 3.14 and tell the user to install
    Python 3.12 or 3.14 instead.  (3.10–3.14 all work.)
    """
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        fail(f"Python 3.10+ is required.  You're on {major}.{minor}.")
        print("  Install Python 3.12 from https://www.python.org/downloads/")
        sys.exit(1)
    if (major, minor) >= (3, 15):
        fail(f"Python {major}.{minor} is too new for some of this project's dependencies.")
        print()
        print(c("33;1", "  scikit-learn / numpy / PyYAML publish Windows wheels only for"))
        print(c("33;1", "  Python versions they've tested.  On very new Python releases,"))
        print(c("33;1", "  pip falls back to building from source — which needs the"))
        print(c("33;1", "  Microsoft Visual C++ Build Tools (~7 GB) and will fail otherwise."))
        print()
        print(c("36;1", "  Recommended fix — install Python 3.12 LTS alongside your current Python:"))
        if IS_WINDOWS:
            print(c("36", "    1. Go to https://www.python.org/downloads/release/python-3128/"))
            print(c("36", "       (or whatever is the latest 3.12.x)"))
            print(c("36", "    2. Download the Windows installer"))
            print(c("36", "    3. Run it — check \"Add python.exe to PATH\" and \"py launcher\""))
            print(c("36", "    4. Re-open the terminal and double-click run.bat — the launcher"))
            print(c("36", "       will automatically pick Python 3.12."))
            print()
            print(c("33;1", "  Alternative: install \"Visual C++ Build Tools\" so pip can compile"))
            print(c("33;1", f"  from source.  Bigger download, takes longer, but keeps your {major}.{minor}."))
        else:
            print(c("36", "    macOS  :  brew install python@3.12"))
            print(c("36", "    Ubuntu :  sudo apt install python3.12 python3.12-venv"))
        print()
        sys.exit(1)


# --------------------------------------------------------------------------- #
# venv + backend dependencies                                                  #
# --------------------------------------------------------------------------- #
def venv_python() -> Path:
    return VENV_DIR / ("Scripts" if IS_WINDOWS else "bin") / ("python.exe" if IS_WINDOWS else "python")


def ensure_venv() -> None:
    if VENV_DIR.exists() and venv_python().exists():
        return
    step(f"Creating Python venv in {VENV_DIR.relative_to(ROOT)} (one-time)…")
    venv.EnvBuilder(with_pip=True, clear=False, upgrade_deps=True).create(str(VENV_DIR))
    ok("Virtual environment created.")


def _pip_install(args: list[str]) -> None:
    cmd = [str(venv_python()), "-m", "pip"] + args
    subprocess.check_call(cmd)


def backend_deps_installed() -> bool:
    """
    Cheap heuristic + sanity check:
      1. Stamp file matches the current requirements.txt hash, AND
      2. A few critical modules actually import (catches interrupted installs).
    """
    stamp = VENV_DIR / ".requirements.sha"
    if not stamp.exists():
        return False
    try:
        if stamp.read_text().strip() != _file_sha(REQUIREMENTS):
            return False
    except Exception:
        return False
    return _critical_modules_importable()


def _critical_modules_importable() -> bool:
    """Make sure uvicorn/fastapi/sqlalchemy/sklearn actually work inside the venv.
    Note: `importlib.util` must be imported explicitly — plain `import importlib`
    does NOT expose `importlib.util` in Python 3.12+."""
    check = (
        "import importlib.util, sys;"
        "missing = [m for m in ('uvicorn','fastapi','sqlalchemy','greenlet','sklearn') "
        "if importlib.util.find_spec(m) is None];"
        "sys.exit(1 if missing else 0)"
    )
    try:
        return subprocess.call(
            [str(venv_python()), "-c", check],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ) == 0
    except Exception:
        return False


def _file_sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_backend_deps() -> None:
    if backend_deps_installed():
        ok("Backend dependencies are up to date.")
        return
    # Remove a stale stamp so that a mid-install Ctrl+C won't leave a lying stamp
    stamp = VENV_DIR / ".requirements.sha"
    if stamp.exists():
        try: stamp.unlink()
        except Exception: pass
    step("Upgrading pip inside the venv…")
    _pip_install(["install", "--upgrade", "pip", "wheel", "setuptools"])
    step("Installing backend dependencies (this can take a minute)…")
    _pip_install(["install", "-r", str(REQUIREMENTS)])
    # Only stamp if the modules really landed
    if not _critical_modules_importable():
        fail("Backend install finished but key modules (uvicorn/fastapi) aren't importable.")
        fail("Try deleting backend/.venv and re-running.")
        sys.exit(1)
    stamp.write_text(_file_sha(REQUIREMENTS))
    ok("Backend dependencies installed.")


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    if ENV_EXAMPLE.exists():
        shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
        ok("Created backend/.env from .env.example")
    else:
        warn(".env.example not found — backend will use built-in defaults.")


# --------------------------------------------------------------------------- #
# Frontend dependencies                                                        #
# --------------------------------------------------------------------------- #
def _which(exe: str) -> str | None:
    return shutil.which(exe + (".cmd" if IS_WINDOWS else "")) or shutil.which(exe)


def ensure_node() -> str | None:
    """Return path to npm, or None if Node.js is missing."""
    return _which("npm")


def _print_node_install_help() -> None:
    fail("Node.js / npm was not found on PATH.")
    print()
    print(c("33;1", "  The React frontend needs Node.js 18+ (LTS) and npm."))
    print()
    if IS_WINDOWS:
        print("  Easiest way on Windows:")
        print(c("36", "    1. Download the LTS installer:  https://nodejs.org/en/download"))
        print(c("36", "    2. Run it — keep all defaults (it adds npm to PATH)"))
        print(c("36", "    3. Close this window, open a NEW terminal, then run run.bat again"))
        print()
        print("  Or with winget (from an admin PowerShell):")
        print(c("36", "    winget install OpenJS.NodeJS.LTS"))
    else:
        print("  Install via your package manager, for example:")
        print(c("36", "    macOS  :  brew install node"))
        print(c("36", "    Ubuntu :  sudo apt install nodejs npm"))
        print(c("36", "    Fedora :  sudo dnf install nodejs npm"))
    print()
    print(c("33;1", "  Tip: to test the backend-only (API + docs) without Node, run:"))
    print(c("36", "       py run.py --backend-only" if IS_WINDOWS else "       python3 run.py --backend-only"))
    print()


def install_frontend_deps(npm: str) -> None:
    node_modules = FRONTEND_DIR / "node_modules"
    if node_modules.exists():
        ok("Frontend dependencies already installed.")
        return
    step("Installing frontend dependencies with npm (this can take a minute)…")
    subprocess.check_call([npm, "install"], cwd=str(FRONTEND_DIR))
    ok("Frontend dependencies installed.")


# --------------------------------------------------------------------------- #
# Process management                                                           #
# --------------------------------------------------------------------------- #
_procs: list[subprocess.Popen] = []


def _stream(proc: subprocess.Popen, label: str, color_code: str) -> None:
    """Pipe a subprocess's stdout to our terminal with a colored label."""
    assert proc.stdout is not None
    prefix = c(color_code, f"[{label}]")
    for raw in iter(proc.stdout.readline, ""):
        line = raw.rstrip()
        if line:
            print(f"{prefix} {line}", flush=True)
    proc.stdout.close()


def backend_command() -> list[str]:
    # Loopback only: the demo ships with admin/admin, so it must not be
    # reachable from other machines on a shared (campus / café) network.
    return [
        str(venv_python()), "-m", "uvicorn", "app.main:app",
        "--host", BACKEND_HOST, "--port", str(BACKEND_PORT),
        "--reload",
    ]


def frontend_command(npm: str) -> list[str]:
    # No `--host`: Vite then listens on localhost only (same reason as above).
    return [npm, "run", "dev", "--", "--port", str(FRONTEND_PORT)]


def start_backend() -> subprocess.Popen:
    step("Starting backend (FastAPI)…")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        backend_command(), cwd=str(BACKEND_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", env=env,
        bufsize=1,
    )
    _procs.append(proc)
    threading.Thread(target=_stream, args=(proc, "backend", "35"), daemon=True).start()
    return proc


def start_frontend(npm: str) -> subprocess.Popen:
    step("Starting frontend (Vite)…")
    env = os.environ.copy()
    env.setdefault("FORCE_COLOR", "1")
    env.setdefault("BROWSER", "none")  # we open the browser ourselves
    proc = subprocess.Popen(
        frontend_command(npm), cwd=str(FRONTEND_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", env=env,
        bufsize=1,
        shell=False,
    )
    _procs.append(proc)
    threading.Thread(target=_stream, args=(proc, "frontend", "36"), daemon=True).start()
    return proc


def wait_for_url(url: str, timeout: float = 60.0) -> bool:
    """Return True once the URL is reachable."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as r:
                if r.status < 500:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


# Ctrl+C is delivered by the OS *and* the `finally:` in __main__ also wants to
# clean up — without a guard, we'd print "Stopping services…" three times and
# (on Windows cmd) require the user to confirm the "Terminate batch job? Y/N"
# prompt twice.  The flag below makes shutdown idempotent.
_shutting_down = False


def shutdown(*_args) -> None:
    global _shutting_down
    if _shutting_down:
        return
    _shutting_down = True

    print()
    step("Stopping services…")
    for p in list(_procs):
        if p.poll() is None:
            try:
                if IS_WINDOWS:
                    # CTRL_BREAK_EVENT is the politest way to ask a child
                    # process group to wind down on Windows.
                    p.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                else:
                    p.terminate()
            except Exception:
                pass
    # Escalate after a grace period
    deadline = time.time() + 5
    while any(p.poll() is None for p in _procs) and time.time() < deadline:
        time.sleep(0.2)
    for p in _procs:
        if p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass
    ok("All services stopped. Bye!")


def _handle_signal(*_args) -> None:
    """SIGINT/SIGTERM handler — shut down once, then exit quietly."""
    shutdown()
    # `os._exit` skips the `atexit` chain so we don't loop through shutdown
    # again on the way out.  Exit code 0 because this was a user-requested
    # quit, not an error.
    os._exit(0)


atexit.register(shutdown)
signal.signal(signal.SIGINT, _handle_signal)
if not IS_WINDOWS:
    signal.signal(signal.SIGTERM, _handle_signal)


# --------------------------------------------------------------------------- #
# Entry point                                                                  #
# --------------------------------------------------------------------------- #
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ovidius NIDS one-click launcher")
    parser.add_argument(
        "--backend-only",
        action="store_true",
        help="Start only the FastAPI backend (useful if Node.js isn't installed yet).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't auto-open the browser.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    banner()
    step(f"Project root: {ROOT}")
    check_python_version()

    # 1) Backend bootstrap
    ensure_env_file()
    ensure_venv()
    install_backend_deps()

    # 2) Frontend bootstrap (unless --backend-only)
    npm: str | None = None
    if not args.backend_only:
        npm = ensure_node()
        if not npm:
            _print_node_install_help()
            warn("Continuing in backend-only mode. Install Node.js and re-run to get the UI.")
            args.backend_only = True  # fall through to backend-only flow
        else:
            install_frontend_deps(npm)

    # 3) Launch backend
    start_backend()

    # 4) Launch frontend (skipped in backend-only mode)
    if not args.backend_only and npm:
        start_frontend(npm)

    # 5) Open the browser once services are ready
    if args.backend_only:
        backend_docs = f"http://localhost:{BACKEND_PORT}/docs"
        step(f"Waiting for backend at {backend_docs} …")
        if wait_for_url(backend_docs, timeout=60):
            ok(f"Backend is ready at {backend_docs}")
            if not args.no_browser:
                try:
                    webbrowser.open(backend_docs)
                except Exception:
                    pass
        else:
            warn("Backend didn't respond in 60s. Check the logs above.")
    else:
        step(f"Waiting for {FRONTEND_URL} …")
        if wait_for_url(FRONTEND_URL, timeout=60):
            if args.no_browser:
                ok("Frontend is ready.")
            else:
                ok(f"Frontend is ready.  Opening {FRONTEND_URL} in your browser…")
                try:
                    webbrowser.open(FRONTEND_URL)
                except Exception:
                    pass
        else:
            warn(f"Frontend didn't respond in 60s. Check the logs above, then open {FRONTEND_URL} manually.")

    print()
    ok(f"Backend API : http://localhost:{BACKEND_PORT}/docs")
    if not args.backend_only:
        ok(f"Frontend UI : {FRONTEND_URL}")
    else:
        warn("Frontend UI : (disabled — backend-only mode)")
    ok("Default login: admin / admin")
    print()
    step("Press Ctrl+C to stop all services.")

    # 6) Supervise: exit when any process dies
    try:
        while True:
            time.sleep(1)
            for p in _procs:
                if p.poll() is not None:
                    fail(f"A process exited with code {p.returncode}. Shutting down the rest…")
                    return
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    # `shutdown` is already wired to atexit + SIGINT/SIGTERM, so we don't need
    # another `finally:` call here — that would just re-run it (and on Windows
    # made the user confirm "Terminate batch job?" twice).
    try:
        main()
    except KeyboardInterrupt:
        # Belt and braces: catch any KeyboardInterrupt that slipped past the
        # signal handler (e.g. raised while we were inside a `time.sleep`).
        pass
