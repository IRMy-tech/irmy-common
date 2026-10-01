import json
import logging
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    def __init__(self, app_name: str, app_id: str):
        super().__init__()
        self.app_name = app_name
        self.app_id = app_id

    def format(self, record: logging.LogRecord) -> str:
        now = datetime.fromtimestamp(record.created, timezone.utc)
        return json.dumps({
            "app_name": self.app_name,
            "app_id": self.app_id,
            "time": now.isoformat(),
            "timestamp": now.timestamp(),
            "level": record.levelname,
            "location": f"{record.filename}:{record.lineno}",
            "message": record.getMessage(),
        })


class _StringFormatter(logging.Formatter):
    def __init__(self, app_name: str, app_id: str):
        super().__init__()
        self.app_name = app_name
        self.app_id = app_id

    def format(self, record: logging.LogRecord) -> str:
        now = datetime.fromtimestamp(record.created, timezone.utc)
        return (
            f"[{now.isoformat()}]"
            f"[{record.levelname}]"
            f"[{self.app_name}({self.app_id})]"
            f"[{record.filename}:{record.lineno}]"
            f" {record.getMessage()}"
        )


def get_logger(
    log_level: str,
    name: str,
    app_name: str,
    app_id: str,
    output_type: str = "json",
) -> logging.Logger:
    if output_type not in ["json", "string"]:
        raise ValueError("Logger output type must be 'json' or 'string'")
    lvl = logging.getLevelName(log_level.upper())
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(lvl)
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(lvl)
    formatter = (
        _JsonFormatter(app_name=app_name, app_id=app_id)
        if output_type == "json"
        else _StringFormatter(app_name=app_name, app_id=app_id)
    )
    h.setFormatter(formatter)
    logger.addHandler(h)
    return logger
