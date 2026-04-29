import logging
import os
import sys
from typing import Optional

LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _level_from_env(default: int = logging.INFO) -> int:
    env_level = os.getenv("LOG_LEVEL", "").upper()
    return LEVEL_MAP.get(env_level, default)


def setup_logger(level: Optional[str | int] = None) -> logging.Logger:
    logger = logging.getLogger("kaspi-notifier")
    if level is not None:
        if isinstance(level, str):
            logger.setLevel(LEVEL_MAP.get(level.upper(), logging.INFO))
        else:
            logger.setLevel(level)
    else:
        logger.setLevel(_level_from_env())

    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
