import json
import logging

from linkhop.logging import JsonFormatter, configure_logging


def _make_record(**overrides) -> logging.LogRecord:
    defaults = {
        "name": "linkhop.test",
        "level": logging.INFO,
        "pathname": __file__,
        "lineno": 10,
        "msg": "hello %s",
        "args": ("world",),
        "exc_info": None,
    }
    defaults.update(overrides)
    return logging.LogRecord(**defaults)


def test_formatter_produces_valid_json():
    out = JsonFormatter().format(_make_record())
    body = json.loads(out)
    assert body["level"] == "INFO"
    assert body["message"] == "hello world"
    assert body["logger"] == "linkhop.test"
    # timestamp must be present and ISO-8601 (parseable) — otherwise log shippers
    # like Loki/Vector reject or mis-bucket the record.
    assert "timestamp" in body
    from datetime import datetime
    datetime.fromisoformat(body["timestamp"])


def test_formatter_includes_exc_info_when_present():
    # Branch coverage for the exc_info path — without this, silently breaking
    # stack-trace emission (e.g. swapping formatException for str) passes review.
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        import sys
        rec = _make_record(exc_info=sys.exc_info())
    body = json.loads(JsonFormatter().format(rec))
    assert "exc_info" in body
    assert "RuntimeError" in body["exc_info"]
    assert "boom" in body["exc_info"]


def test_formatter_emits_extra_context_attrs_and_skips_none():
    # The extra-attrs loop (request_id, path, ...) is the feature that makes
    # request logs useful. Without this test, the loop could be deleted and
    # the suite would stay green.
    rec = _make_record()
    rec.request_id = "abc-123"
    rec.path = "/api/v1/convert"
    rec.status_code = 200
    rec.service = None  # must be skipped, not emitted as null
    body = json.loads(JsonFormatter().format(rec))
    assert body["request_id"] == "abc-123"
    assert body["path"] == "/api/v1/convert"
    assert body["status_code"] == 200
    assert "service" not in body
    # Untouched attrs must also be absent (no accidental key emission).
    assert "method" not in body
    assert "duration_ms" not in body


def test_configure_logging_installs_single_json_handler_at_level():
    # Previously asserted only "no exception raised" — that would miss a
    # regression where the handler isn't attached or the formatter is swapped.
    configure_logging(level="DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
