"""
Frozen entry for the Fancy .exe.

- One .exe (PyInstaller onefile).
- App source lives inside the exe (_MEIPASS while running; nothing copied beside the exe).
- bleak, PySide6, vgamepad, etc. run in the user's Python (pip install).

C extensions cannot be loaded into PyInstaller's embedded interpreter, so we
start ``pythonw main.py --fancy`` from the bundled tree and wait (keeps _MEIPASS valid).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_REQUIRED = ("bleak", "vgamepad", "PySide6", "pystray", "PIL")


def _exe_dir() -> Path:
    return Path(sys.executable).resolve().parent


def _bundle_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", _exe_dir()))


def _find_python() -> Path | None:
    for name in ("pythonw.exe", "python.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)
    for base in (
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("ProgramFiles", ""),
    ):
        if not base:
            continue
        root = Path(base) / "Programs" / "Python"
        if not root.is_dir():
            continue
        for pydir in sorted(root.iterdir(), reverse=True):
            for name in ("pythonw.exe", "python.exe"):
                candidate = pydir / name
                if candidate.is_file():
                    return candidate
    return None


def _python_minor(python: Path) -> str:
    script = "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    try:
        out = subprocess.run(
            [str(python), "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return ""
    if out.returncode != 0:
        return ""
    return (out.stdout or "").strip()


def _message_box(text: str, title: str = "Switch 2 Bridge") -> None:
    if sys.platform != "win32":
        print(f"{title}\n{text}", file=sys.stderr)
        return
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)


def _embedded_minor() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _missing_packages(python: Path) -> list[str]:
    mods = ", ".join(repr(m) for m in _REQUIRED)
    script = (
        "import importlib.util\n"
        f"mods = ({mods},)\n"
        "miss = [m for m in mods if importlib.util.find_spec(m) is None]\n"
        "print(','.join(miss))"
    )
    try:
        out = subprocess.run(
            [str(python), "-c", script],
            capture_output=True,
            text=True,
            timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return ["(could not run Python)"]
    if out.returncode != 0:
        err = (out.stderr or out.stdout or "").strip()
        return [f"(check failed: {err[:200]})"] if err else ["(dependency check failed)"]
    line = (out.stdout or "").strip()
    return [m for m in line.split(",") if m]


def _prepare_frozen() -> tuple[Path, Path] | None:
    bundle = _bundle_dir()
    main_py = bundle / "main.py"
    index_html = bundle / "ui" / "index.html"

    if not main_py.is_file() or not index_html.is_file():
        _message_box(
            "Bundled application files are missing inside the executable.\n"
            "Rebuild with Switch2Bridge-fancy.spec.",
        )
        return None

    python = _find_python()
    if python is None:
        _message_box(
            "Python was not found on PATH.\n\n"
            "Install Python, then run Install dependencies.bat in this folder.",
        )
        return None

    embedded = _embedded_minor()
    user_ver = _python_minor(python)
    if user_ver and embedded != user_ver:
        _message_box(
            f"This .exe was built with Python {embedded}.\n"
            f"The Python on your PATH is {user_ver}.\n\n"
            f"Install Python {embedded}, run Install dependencies.bat, and put "
            f"that Python first on PATH.",
        )
        return None

    missing = _missing_packages(python)
    if missing:
        req = _exe_dir() / "requirements-fancy.txt"
        hint = f'pip install -r "{req}"' if req.is_file() else "pip install -r requirements-fancy.txt"
        _message_box(
            "Required packages are not installed for that Python:\n\n"
            f"  {', '.join(missing)}\n\n"
            f"Run Install dependencies.bat or:\n\n  {hint}\n\n"
            f"Using: {python}",
        )
        return None

    return python, bundle


def _run_app(python: Path, bundle: Path) -> int:
    env = os.environ.copy()
    env["SWITCH2_BRIDGE_INSTALL"] = str(_exe_dir())

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [str(python), str(bundle / "main.py"), "--fancy"],
        cwd=str(bundle),
        env=env,
        creationflags=flags,
        close_fds=True,
    )
    return proc.wait()


def main() -> None:
    if getattr(sys, "frozen", False):
        prepared = _prepare_frozen()
        if prepared is None:
            sys.exit(1)
        python, bundle = prepared
        sys.exit(_run_app(python, bundle))

    if "--fancy" not in sys.argv:
        sys.argv.append("--fancy")
    import main as app_main

    app_main.main()


if __name__ == "__main__":
    main()
