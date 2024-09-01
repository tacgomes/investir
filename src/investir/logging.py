import logging
from typing import Final

from .config import config


class CustomFormatter(logging.Formatter):
    CSI: Final = "\033["
    BRIGHT_CYAN: Final = f"{CSI}96m"
    BOLD_WHITE: Final = f"{CSI}1;37m"
    BRIGHT_YELLOW: Final = f"{CSI}93m"
    RED: Final = f"{CSI}31m"
    BOLD_RED: Final = f"{CSI}1;31m"
    RESET: Final = f"{CSI}0m"

    def __init__(self, fmt: str) -> None:
        super().__init__()
        self.formats = {
            logging.DEBUG: self.BRIGHT_CYAN + fmt + self.RESET,
            logging.INFO: self.BOLD_WHITE + fmt + self.RESET,
            logging.WARNING: self.BRIGHT_YELLOW + fmt + self.RESET,
            logging.ERROR: self.RED + fmt + self.RESET,
            logging.CRITICAL: self.BOLD_RED + fmt + self.RESET,
        }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def configure_logger() -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.NOTSET)

    fmt = "%(levelname)8s | %(message)s"
    console_handler = logging.StreamHandler()
    console_handler.setLevel(config.log_level)
    console_handler.setFormatter(
        CustomFormatter(fmt) if config.use_colour else logging.Formatter(fmt)
    )

    logger.addHandler(console_handler)
