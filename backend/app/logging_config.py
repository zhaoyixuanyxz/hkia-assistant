"""Configure logging for HKIA backend."""

from __future__ import annotations

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(
            logging.Formatter(
                fmt="%(levelname)s %(name)s %(message)s",
            )
        )
        root.addHandler(h)
