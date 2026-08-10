import json
import logging

import pytest

from polymarket_market_discovery.core.logging import configure_logging
from polymarket_market_discovery.settings import get_settings


@pytest.fixture(autouse=True)
def reset_logging() -> None:
    root_logger = logging.getLogger()
    original_level = root_logger.level

    yield

    for handler in list(root_logger.handlers):
        if handler.name and handler.name.startswith(
            "polymarket_market_discovery_jsonl_"
        ):
            root_logger.removeHandler(handler)
            handler.close()

    root_logger.setLevel(original_level)
    get_settings.cache_clear()


def test_configure_logging_writes_jsonl_to_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("POLYMARKET_DISCOVERY_LOG_LEVEL", "DEBUG")
    get_settings.cache_clear()

    configure_logging()
    configure_logging()

    root_logger = logging.getLogger()
    handlers = [
        handler
        for handler in root_logger.handlers
        if handler.name
        and handler.name.startswith("polymarket_market_discovery_jsonl_")
    ]

    assert len(handlers) == 1
    assert root_logger.level == logging.DEBUG

    logging.getLogger("tests.logging").info(
        "Test event",
        extra={"event": "test.event", "context": {"ok": True}},
    )

    stdout_line = capsys.readouterr().out.strip()
    stdout_payload = json.loads(stdout_line)

    assert stdout_payload["event"] == "test.event"
    assert stdout_payload["context"] == {"ok": True}
