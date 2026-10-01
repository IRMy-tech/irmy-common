import json
import logging
import time

from irmy_common import get_logger
from irmy_common._logger import _JsonFormatter


def test_json_uses_record_time():
    formatter = _JsonFormatter(app_name="app", app_id="id")
    record = logging.LogRecord("n", logging.INFO, __file__, 1, "hello", None, None)
    record.created = time.time() - 3600
    out = json.loads(formatter.format(record))
    assert abs(out["timestamp"] - record.created) < 0.001
    assert out["message"] == "hello"


def test_get_logger_does_not_duplicate_handlers():
    get_logger("INFO", "dup", "app", "id")
    logger = get_logger("DEBUG", "dup", "app", "id", output_type="string")
    assert len(logger.handlers) == 1
    assert logger.level == logging.DEBUG
