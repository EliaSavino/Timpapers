"""Central logging config."""

from __future__ import annotations

import logging


def configure_logging() -> None:
    """Configure process-wide structured-ish logging."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
