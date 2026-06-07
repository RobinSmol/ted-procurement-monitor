import logging
import os
from datetime import datetime


def setup_logger() -> logging.Logger:
    """Configures and returns the global logger for the TED pipeline.

    Sets up dual output — a rotating monthly log file under logs/ and
    a stdout stream handler. Silences the httpx logger to keep output
    clean during API calls. Safe to call multiple times as
    logging.basicConfig is a no-op if handlers are already registered.

    Returns:
        The configured Logger instance for the TED_ETL namespace.
    """
    if not os.path.exists("logs"):
        os.makedirs("logs")

    log_filename = f"logs/ted_pipeline_{datetime.now().strftime('%Y-%m')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_filename, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logging.getLogger("TED_ETL")
