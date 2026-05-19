"""File logging — always on when running via pythonw (no console)."""

import logging
import os
import sys

from bridge.paths import install_root

LOG_DIR = install_root() / "logs"
LOG_FILE = LOG_DIR / "bridge.log"
_BRIDGE_LOG = logging.getLogger("switch2_bridge")
_LOGGING_READY = False


def setup_logging() -> Path:
    """Write DEBUG logs to logs/bridge.log; mirror INFO+ to console when present."""
    global _LOGGING_READY
    if _LOGGING_READY:
        return LOG_FILE

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _BRIDGE_LOG.setLevel(logging.DEBUG)
    _BRIDGE_LOG.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d %(levelname)-8s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    _BRIDGE_LOG.addHandler(fh)

    if sys.stdout is not None and hasattr(sys.stdout, "write"):
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        _BRIDGE_LOG.addHandler(ch)

    for name in ("bleak", "bleak.backends"):
        bl = logging.getLogger(name)
        bl.setLevel(logging.DEBUG)
        bl.handlers.clear()
        bl.addHandler(fh)
        bl.propagate = False

    _LOGGING_READY = True
    _BRIDGE_LOG.info("=" * 72)
    _BRIDGE_LOG.info("Session started  pid=%s  python=%s", os.getpid(), sys.version.split()[0])
    _BRIDGE_LOG.info("Log file: %s", LOG_FILE)
    return LOG_FILE


def log(msg: str, level: int = logging.INFO):
    if not _LOGGING_READY:
        setup_logging()
    _BRIDGE_LOG.log(level, msg)
    if level >= logging.WARNING and sys.stderr is not None:
        try:
            print(msg, flush=True, file=sys.stderr)
        except Exception:
            pass


def log_debug(msg: str):
    log(msg, logging.DEBUG)


def log_exception(msg: str):
    if not _LOGGING_READY:
        setup_logging()
    _BRIDGE_LOG.exception(msg)
