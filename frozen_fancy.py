"""
Frozen entry for the Fancy .exe.

- One .exe (PyInstaller onefile).
- App source lives inside the exe (_MEIPASS while running; nothing copied beside the exe).
- bleak, PySide6, vgamepad, etc. run in the user's Python (pip install).

C extensions cannot be loaded into PyInstaller's embedded interpreter, so we
start ``pythonw main.py --fancy`` from the bundled tree and wait (keeps _MEIPASS valid).

On first run, missing packages are installed automatically via pip (needs Python on PATH).
No log files are written beside the .exe.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_IMPORT_CHECKS: tuple[tuple[str, str], ...] = (
    ("bleak", "bleak"),
    ("vgamepad", "vgamepad"),
    ("pystray", "pystray"),
    ("PIL", "Pillow"),
    ("PySide6.QtWebEngineWidgets", "PySide6 (WebEngine)"),
)

_VERSION_FILE = "python_version.txt"
_REQUIREMENTS_NAME = "requirements-fancy.txt"

_MB_ICONERROR = 0x10
_MB_ICONINFORMATION = 0x40


def _exe_dir() -> Path:
    return Path(sys.executable).resolve().parent


def _bundle_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", _exe_dir()))


def _requirements_path() -> Path | None:
    for base in (_exe_dir(), _bundle_dir()):
        path = base / _REQUIREMENTS_NAME
        if path.is_file():
            return path
    return None


def _recommended_minor() -> str | None:
    for base in (_exe_dir(), _bundle_dir()):
        path = base / _VERSION_FILE
        if path.is_file():
            line = path.read_text(encoding="utf-8").strip().splitlines()
            if line:
                return line[0].strip()
    return None


def _remove_legacy_python_config() -> None:
    """Remove old sidecar file from earlier releases (no longer used)."""
    try:
        (_exe_dir() / ".switch2-bridge-python").unlink(missing_ok=True)
    except OSError:
        pass


def _to_python_exe(python: Path) -> Path:
    if python.name.lower() == "python.exe":
        return python
    sibling = python.parent / "python.exe"
    return sibling if sibling.is_file() else python


def _to_pythonw(python_exe: Path) -> Path:
    sibling = python_exe.parent / "pythonw.exe"
    return sibling if sibling.is_file() else python_exe


def _iter_python_candidates() -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []

    def add(path: Path | None) -> None:
        if path is None or not path.is_file():
            return
        key = str(path.resolve()).lower()
        if key in seen:
            return
        seen.add(key)
        out.append(path)

    for name in ("python.exe", "pythonw.exe"):
        found = shutil.which(name)
        add(Path(found) if found else None)

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
            add(pydir / "python.exe")
            add(pydir / "pythonw.exe")
    return out


def _python_minor(python: Path) -> str:
    script = "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    try:
        out = subprocess.run(
            [str(_to_python_exe(python)), "-c", script],
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


def _find_python_exe(preferred_minor: str | None = None) -> Path | None:
    candidates = [_to_python_exe(p) for p in _iter_python_candidates()]

    if preferred_minor:
        for exe in candidates:
            if _python_minor(exe) == preferred_minor:
                return exe

    return candidates[0] if candidates else None


def _message_box(text: str, title: str = "Switch 2 Bridge", *, icon: int = _MB_ICONERROR) -> None:
    if sys.platform != "win32":
        print(f"{title}\n{text}", file=sys.stderr)
        return
    import ctypes

    ctypes.windll.user32.MessageBoxW(0, text, title, icon)


def _missing_packages(python_exe: Path) -> list[str]:
    checks = ", ".join(repr(m) for m, _ in _IMPORT_CHECKS)
    script = (
        "import importlib\n"
        f"checks = ({checks},)\n"
        "miss = []\n"
        "for m in checks:\n"
        "    try:\n"
        "        importlib.import_module(m)\n"
        "    except Exception as e:\n"
        "        miss.append(f'{m} ({e.__class__.__name__}: {e})')\n"
        "print('\\n'.join(miss))"
    )
    try:
        out = subprocess.run(
            [str(python_exe), "-c", script],
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        return [f"(could not run Python: {exc})"]
    if out.returncode != 0:
        err = (out.stderr or out.stdout or "").strip()
        return [f"(import check failed: {err[:300]})"] if err else ["(import check failed)"]
    return [ln.strip() for ln in (out.stdout or "").splitlines() if ln.strip()]


def _pip_install_args(*parts: str) -> list[str]:
    return ["install", "--no-cache-dir", *parts]


def _clear_pip_cache(python_exe: Path) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for args in (["cache", "remove", "vgamepad"], ["cache", "purge"]):
        subprocess.run(
            [str(python_exe), "-m", "pip", *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )


def _run_pip_step(python_exe: Path, args: list[str]) -> int:
    """Run pip with a visible console (no log files)."""
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    proc = subprocess.run(
        [str(python_exe), "-m", "pip", *args],
        creationflags=flags,
    )
    return proc.returncode


def _install_dependencies(python_exe: Path) -> bool:
    req = _requirements_path()
    if req is None:
        _message_box(
            f"{_REQUIREMENTS_NAME} was not found inside the app or beside the .exe.\n"
            "Re-download the Fancy release or rebuild the installer.",
        )
        return False

    _message_box(
        "First-time setup: installing Python packages (~650 MB).\n\n"
        "A console window will show download progress. This can take several minutes.\n"
        "You only need to do this once.",
        title="Switch 2 Bridge",
        icon=_MB_ICONINFORMATION,
    )

    if _run_pip_step(python_exe, _pip_install_args("--upgrade", "pip")) != 0:
        _message_box(
            "Could not upgrade pip.\n\n"
            "Check the console window for details, then try again.",
        )
        return False

    code = _run_pip_step(python_exe, _pip_install_args("-r", str(req)))
    if code != 0:
        _clear_pip_cache(python_exe)
        code = _run_pip_step(python_exe, _pip_install_args("-r", str(req)))
    if code != 0:
        _message_box(
            "Package install failed.\n\n"
            "Check the console window for details.\n\n"
            "If you see Permission denied on a .whl file, close Switch 2 Bridge "
            "and any game using the controller, then run again.",
        )
        return False

    return True


def _prepare_frozen() -> tuple[Path, Path] | None:
    _remove_legacy_python_config()
    bundle = _bundle_dir()
    main_py = bundle / "main.py"
    index_html = bundle / "ui" / "index.html"

    if not main_py.is_file() or not index_html.is_file():
        _message_box(
            "Bundled application files are missing inside the executable.\n"
            "Rebuild with Switch2Bridge-fancy.spec.",
        )
        return None

    recommended = _recommended_minor()
    python_exe = _find_python_exe(recommended)

    if python_exe is None:
        ver_hint = f" {recommended}" if recommended else ""
        _message_box(
            f"Python{ver_hint} was not found.\n\n"
            "Install Python from https://www.python.org/downloads/\n"
            "Enable \"Add python.exe to PATH\", then run this program again.",
        )
        return None

    user_ver = _python_minor(python_exe)
    if recommended and user_ver and user_ver != recommended:
        _message_box(
            f"This release was built for Python {recommended}.\n"
            f"Found Python {user_ver}:\n  {python_exe}\n\n"
            f"Install Python {recommended} (64-bit) with \"Add to PATH\", then run again.",
        )
        return None

    missing = _missing_packages(python_exe)
    if missing:
        if not _install_dependencies(python_exe):
            return None
        missing = _missing_packages(python_exe)
        if missing:
            detail = "\n".join(f"  • {m}" for m in missing[:6])
            _message_box(
                "Packages are still missing after install:\n\n"
                f"{detail}",
            )
            return None

    return _to_pythonw(python_exe), bundle


def _run_app(python: Path, bundle: Path) -> int:
    env = os.environ.copy()
    env["SWITCH2_BRIDGE_INSTALL"] = str(_exe_dir())
    env["SWITCH2_BRIDGE_NO_LOGS"] = "1"

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [str(python), str(bundle / "main.py"), "--fancy"],
        cwd=str(bundle),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=flags,
        close_fds=True,
    )
    output, _ = proc.communicate()
    code = proc.returncode

    if code != 0:
        tail = (output or "").strip()[-1200:]
        _message_box(
            "Switch 2 Bridge closed with an error.\n\n"
            f"Exit code: {code}\n\n"
            f"{tail}".strip() or "(no error output captured)",
        )
    _remove_legacy_python_config()
    return code


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
