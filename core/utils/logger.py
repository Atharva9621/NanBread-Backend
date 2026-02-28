"""
logger.py
---------
A Rich-backed logger with:
  - 5 verbosity levels  : ERROR < WARN < INFO < DEBUG < TRACE
  - Callable interface  : log("msg"), log.info("msg"), etc.
  - Public console      : Logger.console  (class-level, shared across instances)
  - Optional file sink  : plain-text only, auto-named with run timestamp
  - Logging is a second-class citizen — everything is wrapped in try/except:
      1. Rich console failure  → falls back to plain-text file write
      2. File write failure    → emits ONE plain print() across ALL instances
                                 (guarded by module-level flag)
      3. raise_exceptions=True → re-raises after the fallback chain
"""

from __future__ import annotations

import re
import os
from datetime import datetime
from enum import IntEnum

from rich.console import Console
from rich.theme import Theme


# ---------------------------------------------------------------------------
# Module-level "already warned" flag  — one print across all Logger instances
# ---------------------------------------------------------------------------
_FILE_ERROR_REPORTED: bool = False


# ---------------------------------------------------------------------------
# Verbosity levels
# ---------------------------------------------------------------------------

class Verbosity(IntEnum):
    ERROR = 0
    WARN  = 1
    INFO  = 2
    DEBUG = 3
    TRACE = 4


# ---------------------------------------------------------------------------
# Colour theme  (avoiding stock red / green / yellow)
# ---------------------------------------------------------------------------

_THEME = Theme({
    "lvl.error": "bold bright_magenta",
    "lvl.warn":  "bold orange3",
    "lvl.info":  "bold cyan",
    "lvl.debug": "bold blue_violet",
    "lvl.trace": "bold grey58",
})

_LEVEL_STYLE = {
    Verbosity.ERROR: ("lvl.error", "ERROR"),
    Verbosity.WARN:  ("lvl.warn",  "WARN "),
    Verbosity.INFO:  ("lvl.info",  "INFO "),
    Verbosity.DEBUG: ("lvl.debug", "DEBUG"),
    Verbosity.TRACE: ("lvl.trace", "TRACE"),
}

_MARKUP_RE = re.compile(r"\[/?[^\[\]]*\]")


def _strip_markup(text: str) -> str:
    return _MARKUP_RE.sub("", text)


def _plain_line(label: str, name: str, msg: str) -> str:
    ts = datetime.now().strftime("%H:%M:%S")
    return f"[{ts}] [{label}] ({name}) {_strip_markup(msg)}\n"


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

class Logger:
    # Class-level shared console — override per instance if needed
    console: Console = Console(theme=_THEME)

    def __init__(
        self,
        name: str = "app",
        verbosity: Verbosity = Verbosity.TRACE,
        log_to_file: bool = False,
        log_dir: str = "logs",
        log_file: str | None = None,
        raise_exceptions: bool = True,
    ) -> None:
        self.name = name
        self.verbosity = verbosity
        self.raise_exceptions = raise_exceptions
        self._file_handle = None

        if log_to_file:
            try:
                if log_file:
                    log_path = os.path.join(log_dir, log_file)
                else:
                    os.makedirs(log_dir, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_path = os.path.join(log_dir, f"{name}_{timestamp}.log")
                self._file_handle = open(log_path, "w", encoding="utf-8")
            except Exception as exc:
                self._handle_file_error(exc)

    # ------------------------------------------------------------------
    # Fallback helpers
    # ------------------------------------------------------------------

    def _try_write_file(self, line: str) -> None:
        """Write plain text to file. On failure → one-time print fallback."""
        global _FILE_ERROR_REPORTED
        try:
            if self._file_handle:
                self._file_handle.write(line)
                self._file_handle.flush()
        except Exception as exc:
            self._handle_file_error(exc)

    def _handle_file_error(self, exc: Exception) -> None:
        """Emit a single plain print to console for file errors, exactly once."""
        global _FILE_ERROR_REPORTED
        if not _FILE_ERROR_REPORTED:
            _FILE_ERROR_REPORTED = True
            sep = "=" * 60
            print(sep)
            print(f"  LOGGER FILE ERROR ({self.name}): {exc}")
            print(f"  Further file-write failures will be silently ignored.")
            print(sep)
        if self.raise_exceptions:
            raise exc

    # ------------------------------------------------------------------
    # Core emit
    # ------------------------------------------------------------------

    def _emit(self, level: Verbosity, msg: str) -> None:
        _, label = _LEVEL_STYLE[level]
        plain_line = _plain_line(label, self.name, msg)

        # Always attempt file write (verbosity gate does NOT apply to file)
        self._try_write_file(plain_line)

        # Console is gated by verbosity
        if level > self.verbosity:
            return

        style, _ = _LEVEL_STYLE[level]
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = (
            f"[{style}]\\[{ts}][/{style}] "
            f"[{style}]{label}[/{style}] "
            f"[dim]({self.name})[/dim]"
        )

        try:
            self.console.print(f"{prefix}  {msg}")
        except Exception as rich_exc:
            # Rich failed — fall back to plain-text file write
            fallback = _plain_line(f"{label}+RICH_ERR", self.name, msg)
            self._try_write_file(
                f"[LOGGER] Rich console error: {rich_exc}\n"
                f"{fallback}"
            )
            if self.raise_exceptions:
                raise rich_exc

    # ------------------------------------------------------------------
    # Public level methods
    # ------------------------------------------------------------------

    def error(self, msg: str) -> None:
        self._emit(Verbosity.ERROR, msg)

    def warn(self, msg: str) -> None:
        self._emit(Verbosity.WARN, msg)

    def info(self, msg: str) -> None:
        self._emit(Verbosity.INFO, msg)

    def debug(self, msg: str) -> None:
        self._emit(Verbosity.DEBUG, msg)

    def trace(self, msg: str) -> None:
        self._emit(Verbosity.TRACE, msg)

    # ------------------------------------------------------------------
    # log() + __call__
    # ------------------------------------------------------------------

    def log(self, msg: str, level: Verbosity = Verbosity.INFO) -> None:
        """Generic log — defaults to INFO, or pass level= to override."""
        self._emit(level, msg)

    def __call__(self, msg: str, level: Verbosity = Verbosity.INFO) -> None:
        """logger('msg') is shorthand for logger.log('msg')."""
        self._emit(level, msg)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def set_verbosity(self, verbosity: Verbosity) -> None:
        self.verbosity = verbosity

    def close(self) -> None:
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

    def __repr__(self) -> str:
        return f"<Logger name={self.name!r} verbosity={self.verbosity.name}>"


# ---------------------------------------------------------------------------
# Quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log = Logger(name="demo", verbosity=Verbosity.TRACE, log_to_file=True)

    log("App starting up")
    log.info("Found [blue]32[/blue] residual vars → [bold]False[/bold]")
    log.debug("Batch size [cyan]64[/cyan], lr [magenta]1e-3[/magenta]")
    log.trace("Entering forward pass")
    log.warn("Checkpoint [yellow]missing[/yellow], starting fresh")
    log.error("CUDA OOM — [bold bright_red]halting run[/bold bright_red]")

    log.set_verbosity(Verbosity.WARN)
    log.info("This info msg is silenced on console but still written to file")
    log.warn("This warn still shows")

    log.console.rule("[bold]run complete[/bold]")
    log.close()