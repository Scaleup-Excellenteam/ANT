"""Central logging configuration for the autocomplete application."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = REPO_ROOT / "logs" / "app.log"
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3
_HANDLER_MARKER = "_autocomplete_rotating_file_handler"


def _resolve_level(level: Optional[Union[str, int]]) -> int:
    if isinstance(level, int):
        return level
    name = (level or os.getenv("AUTOCOMPLETE_LOG_LEVEL", DEFAULT_LOG_LEVEL)).upper()
    resolved = logging.getLevelName(name)
    if not isinstance(resolved, int):
        raise ValueError(f"Unknown log level: {name}")
    return resolved


def configure_logging(
    level: Optional[Union[str, int]] = None,
    log_path: Optional[Union[str, Path]] = None,
) -> Path:
    """Configure one rotating application log handler and return its path.

    Repeated calls are safe and do not duplicate handlers. The path and level can
    be overridden with ``AUTOCOMPLETE_LOG_FILE`` and ``AUTOCOMPLETE_LOG_LEVEL``.
    """

    configured_path = Path(
        log_path or os.getenv("AUTOCOMPLETE_LOG_FILE", str(DEFAULT_LOG_PATH))
    ).expanduser().resolve()
    configured_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_level = _resolve_level(level)

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            if Path(handler.baseFilename) == configured_path:
                handler.setLevel(resolved_level)
                root_logger.setLevel(min(root_logger.level or resolved_level, resolved_level))
                return configured_path
            root_logger.removeHandler(handler)
            handler.close()
            break

    handler = RotatingFileHandler(
        configured_path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(resolved_level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(handler)
    root_logger.setLevel(min(root_logger.level or resolved_level, resolved_level))
    return configured_path
