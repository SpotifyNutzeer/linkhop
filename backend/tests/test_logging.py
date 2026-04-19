import json
import logging

from linkhop.logging import configure_logging, JsonFormatter


def test_formatter_produces_valid_json():
    fmt = JsonFormatter()
    rec = logging.LogRecord(
        name="linkhop.test", level=logging.INFO, pathname=__file__, lineno=10,
        msg="hello %s", args=("world",), exc_info=None,
    )
    out = fmt.format(rec)
    body = json.loads(out)
    assert body["level"] == "INFO"
    assert body["message"] == "hello world"
    assert body["logger"] == "linkhop.test"


def test_configure_logging_runs():
    configure_logging(level="DEBUG")
    logging.getLogger("linkhop.test").info("check")
