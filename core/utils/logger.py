"""
logger.py
---------
A Rich-backed logger with:
  - 5 verbosity levels  : ERROR < WARN < INFO < DEBUG < TRACE
  - Callable interface  : log("msg"), log.info("msg"), etc.
  - Public console      : Logger.console  (class-level, shared across instances)
  - Optional file sink  : plain-text only, auto-named with run timestamp
  - Logging is a second-class citizen — everything is wrapped in try/except

USE_RICH_LOGGING env var:
  "true" / "1" / "yes"  (default) → Rich console output
  "false" / "0" / "no"            → stdlib logging, no Rich import at all
  Rich markup in messages is stripped to known tags only in stdlib mode.
"""

from __future__ import annotations

import os
import re
import logging as _stdlib_logging
from datetime import datetime
from enum import IntEnum

from dotenv import load_dotenv
load_dotenv()
# ---------------------------------------------------------------------------
# Resolve USE_RICH_LOGGING once at import time — no Rich import if disabled
# ---------------------------------------------------------------------------

_USE_RICH = os.environ.get("USERICHLOGGING", "true").strip().lower() not in (
    "false", "0", "no"
)

if _USE_RICH:
    from rich.console import Console
    from rich.theme import Theme
else:
    Console = None
    Theme   = None


# ---------------------------------------------------------------------------
# Module-level file-error flag — one print across ALL Logger instances
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
# Targeted Rich markup stripping for stdlib mode
#
# We only strip tags whose content matches known Rich color/style names.
# Unknown [*] patterns are left untouched — they might be part of log content.
# ---------------------------------------------------------------------------

_RICH_KNOWN_TAGS = {
    # basic colours
    "black","red","green","yellow","blue","magenta","cyan","white",
    # bright variants
    "bright_black","bright_red","bright_green","bright_yellow",
    "bright_blue","bright_magenta","bright_cyan","bright_white",
    # styles
    "bold","dim","italic","underline","blink","reverse","strike",
    # extended colours used in this codebase
    "orange3","blue_violet","grey58","green1","cyan1",
    # compound styles (order matters — longer first in regex)
    "bold green","bold red","bold cyan","bold blue","bold magenta",
    "bold orange3","bold bright_magenta","bold blue_violet","bold grey58",
    "bold bright_red","bold bright_green",
}

_KNOWN_TAGS_RE = re.compile(
    r"\[(?:/)?" +
    "(?:" + "|".join(re.escape(t) for t in sorted(_RICH_KNOWN_TAGS, key=len, reverse=True)) + ")" +
    r"\]",
    re.IGNORECASE,
)
_BARE_CLOSE_RE  = re.compile(r"\[/\]")
_ALL_MARKUP_RE  = re.compile(r"\[/?[^\[\]]*\]")   # used for file sink only


def strip_rich_markup(text: str) -> str:
    """Strip ONLY known Rich color/style tags. Leaves unknown [*] alone."""
    text = _KNOWN_TAGS_RE.sub("", text)
    text = _BARE_CLOSE_RE.sub("", text)
    return text


def _strip_all_markup(text: str) -> str:
    """Strip all [*] patterns — safe for file sink (our own logs only)."""
    return _ALL_MARKUP_RE.sub("", text)


def _plain_line(label: str, name: str, msg: str) -> str:
    ts = datetime.now().strftime("%H:%M:%S")
    return f"[{ts}] [{label}] ({name}) {_strip_all_markup(msg)}\n"


# ---------------------------------------------------------------------------
# Rich theme + level map
# ---------------------------------------------------------------------------

if _USE_RICH:
    _THEME = Theme({
        "lvl.error": "bold bright_magenta",
        "lvl.warn":  "bold orange3",
        "lvl.info":  "bold cyan",
        "lvl.debug": "bold blue_violet",
        "lvl.trace": "bold grey58",
    })
else:
    _THEME = None

_LEVEL_STYLE = {
    Verbosity.ERROR: ("lvl.error", "ERROR"),
    Verbosity.WARN:  ("lvl.warn",  "WARN "),
    Verbosity.INFO:  ("lvl.info",  "INFO "),
    Verbosity.DEBUG: ("lvl.debug", "DEBUG"),
    Verbosity.TRACE: ("lvl.trace", "TRACE"),
}

_STDLIB_LEVEL = {
    Verbosity.ERROR: _stdlib_logging.ERROR,
    Verbosity.WARN:  _stdlib_logging.WARNING,
    Verbosity.INFO:  _stdlib_logging.INFO,
    Verbosity.DEBUG: _stdlib_logging.DEBUG,
    Verbosity.TRACE: _stdlib_logging.DEBUG,   # stdlib has no TRACE
}


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

class Logger:
    console: Console = Console(theme=_THEME) if _USE_RICH else None

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

        # stdlib logger — always set up, used when _USE_RICH is False
        self._stdlib = _stdlib_logging.getLogger(name)
        if not self._stdlib.handlers:
            _h = _stdlib_logging.StreamHandler()
            _h.setFormatter(_stdlib_logging.Formatter(
                "[%(asctime)s] [%(levelname)-5s] (%(name)s)  %(message)s",
                datefmt="%H:%M:%S",
            ))
            self._stdlib.addHandler(_h)
        self._stdlib.setLevel(_STDLIB_LEVEL.get(verbosity, _stdlib_logging.DEBUG))
        self._stdlib.propagate = False

        if log_to_file:
            try:
                if log_file:
                    log_path = os.path.join(log_dir, log_file)
                else:
                    os.makedirs(log_dir, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_path = os.path.join(log_dir, f"{name}_{ts}.log")
                self._file_handle = open(log_path, "w", encoding="utf-8")
            except Exception as exc:
                self._handle_file_error(exc)

    # ------------------------------------------------------------------
    # Fallback helpers
    # ------------------------------------------------------------------

    def _try_write_file(self, line: str) -> None:
        global _FILE_ERROR_REPORTED
        try:
            if self._file_handle:
                self._file_handle.write(line)
                self._file_handle.flush()
        except Exception as exc:
            self._handle_file_error(exc)

    def _handle_file_error(self, exc: Exception) -> None:
        global _FILE_ERROR_REPORTED
        if not _FILE_ERROR_REPORTED:
            _FILE_ERROR_REPORTED = True
            sep = "=" * 60
            print(f"{sep}\n  LOGGER FILE ERROR ({self.name}): {exc}\n  Further file-write failures will be silently ignored.\n{sep}")
        if self.raise_exceptions:
            raise exc

    # ------------------------------------------------------------------
    # Core emit
    # ------------------------------------------------------------------

    def _emit(self, level: Verbosity, msg: str) -> None:
        _, label = _LEVEL_STYLE[level]
        self._try_write_file(_plain_line(label, self.name, msg))

        if level > self.verbosity:
            return

        if _USE_RICH:
            self._emit_rich(level, label, msg)
        else:
            self._emit_stdlib(level, msg)

    def _emit_rich(self, level: Verbosity, label: str, msg: str) -> None:
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
            self._try_write_file(
                f"[LOGGER] Rich error: {rich_exc}\n"
                f"{_plain_line(f'{label}+RICH_ERR', self.name, msg)}"
            )
            if self.raise_exceptions:
                raise rich_exc

    def _emit_stdlib(self, level: Verbosity, msg: str) -> None:
        clean = strip_rich_markup(msg)
        self._stdlib.log(_STDLIB_LEVEL.get(level, _stdlib_logging.DEBUG), clean)

    # ------------------------------------------------------------------
    # Public level methods
    # ------------------------------------------------------------------

    def error(self, msg: str) -> None: self._emit(Verbosity.ERROR, msg)
    def warn(self,  msg: str) -> None: self._emit(Verbosity.WARN,  msg)
    def warning(self,  msg: str) -> None: self._emit(Verbosity.WARN,  msg)
    def info(self,  msg: str) -> None: self._emit(Verbosity.INFO,  msg)
    def debug(self, msg: str) -> None: self._emit(Verbosity.DEBUG, msg)
    def trace(self, msg: str) -> None: self._emit(Verbosity.TRACE, msg)

    def log(self, msg: str, level: Verbosity = Verbosity.INFO) -> None:
        self._emit(level, msg)

    def __call__(self, msg: str, level: Verbosity = Verbosity.INFO) -> None:
        self._emit(level, msg)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def set_verbosity(self, verbosity: Verbosity) -> None:
        self.verbosity = verbosity
        self._stdlib.setLevel(_STDLIB_LEVEL.get(verbosity, _stdlib_logging.DEBUG))

    def close(self) -> None:
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

    def __repr__(self) -> str:
        return f"<Logger name={self.name!r} verbosity={self.verbosity.name} rich={_USE_RICH}>"


# ---------------------------------------------------------------------------
# Quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log = Logger(name="demo", verbosity=Verbosity.TRACE)

    log("App starting up")
    log.info("Found [blue]32[/blue] residual vars → [bold]False[/bold]")
    log.debug("Batch size [cyan]64[/cyan], lr [magenta]1e-3[/magenta]")
    log.trace("Entering forward pass")
    log.warn("Checkpoint [yellow]missing[/yellow], starting fresh")
    log.error("CUDA OOM — [bold bright_red]halting run[/bold bright_red]")

    log.set_verbosity(Verbosity.WARN)
    log.info("Silenced on console, still written to file if enabled")
    log.warn("This warn still shows")

    if _USE_RICH and log.console:
        log.console.rule("[bold]run complete[/bold]")

    log.close()