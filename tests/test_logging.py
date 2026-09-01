import logging

from src.logging_config import (
    BACKUP_COUNT,
    MAX_LOG_BYTES,
    configure_logging,
)


def _application_handlers():
    return [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "_autocomplete_rotating_file_handler", False)
    ]


def _remove_application_handlers():
    root = logging.getLogger()
    for handler in _application_handlers():
        root.removeHandler(handler)
        handler.close()


def test_configure_logging_writes_expected_format_and_rotation_settings(tmp_path):
    _remove_application_handlers()
    log_path = tmp_path / "nested" / "app.log"
    try:
        configured_path = configure_logging(level="DEBUG", log_path=log_path)
        logging.getLogger("matching").info('Query received: "python"')
        handler = _application_handlers()[0]
        handler.flush()

        output = log_path.read_text(encoding="utf-8")
        assert configured_path == log_path.resolve()
        assert " | INFO | matching | Query received:" in output
        assert handler.maxBytes == MAX_LOG_BYTES
        assert handler.backupCount == BACKUP_COUNT
    finally:
        _remove_application_handlers()


def test_configure_logging_is_idempotent(tmp_path):
    _remove_application_handlers()
    try:
        configure_logging(log_path=tmp_path / "app.log")
        configure_logging(log_path=tmp_path / "app.log")
        assert len(_application_handlers()) == 1
    finally:
        _remove_application_handlers()


def test_configure_logging_can_change_output_path(tmp_path):
    _remove_application_handlers()
    first_path = tmp_path / "first.log"
    second_path = tmp_path / "second.log"
    try:
        configure_logging(log_path=first_path)
        configure_logging(log_path=second_path)
        logging.getLogger("application").warning("new destination")
        _application_handlers()[0].flush()

        assert len(_application_handlers()) == 1
        assert "new destination" not in first_path.read_text(encoding="utf-8")
        assert "new destination" in second_path.read_text(encoding="utf-8")
    finally:
        _remove_application_handlers()


def test_invalid_log_level_is_rejected(tmp_path):
    _remove_application_handlers()
    try:
        try:
            configure_logging(level="NOT_A_LEVEL", log_path=tmp_path / "app.log")
        except ValueError as exc:
            assert "Unknown log level" in str(exc)
        else:
            raise AssertionError("Expected invalid logging level to fail")
    finally:
        _remove_application_handlers()
