import logging
import logging.config
from typing import Final

from investir.config import config


class CustomFormatter(logging.Formatter):
    CSI: Final = "\033["
    MAGENTA: Final = f"{CSI}35m"
    BLUE: Final = f"{CSI}34m"
    BRIGHT_YELLOW: Final = f"{CSI}93m"
    RED: Final = f"{CSI}31m"
    BOLD_RED: Final = f"{CSI}1;31m"
    RESET: Final = f"{CSI}0m"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        fmt = kwargs.get("fmt", "%(message)s")

        self.formats = {
            logging.DEBUG: f"{self.MAGENTA}{fmt}{self.RESET}",
            logging.INFO: f"{self.BLUE}{fmt}{self.RESET}",
            logging.WARNING: f"{self.BRIGHT_YELLOW}{fmt}{self.RESET}",
            logging.ERROR: f"{self.RED}{fmt}{self.RESET}",
            logging.CRITICAL: f"{self.BOLD_RED}{fmt}{self.RESET}",
        }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def configure_logger() -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": True,
            "formatters": {
                "standard": {
                    "()": CustomFormatter if config.use_colour else logging.Formatter,
                    "format": "%(levelname)8s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                },
            },
            "loggers": {
                "root": {"level": "NOTSET", "handlers": ["console"]},
                "investir": {"level": config.log_level},
                "yfinance": {"level": logging.CRITICAL},
            },
        }
    )
