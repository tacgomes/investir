import logging
from typing import Final


class CustomFormatter(logging.Formatter):
    LIGHT_CYAN: Final = "\033[0;96m"
    GREEN: Final = "\033[0;32m"
    YELLOW: Final = "\033[38;5;226m"
    RED: Final = "\033[38;5;196m"
    BOLD_RED: Final = "\033[31;1m"
    RESET: Final = "\033[0m"

    def __init__(self, fmt: str) -> None:
        super().__init__()
        self.formats = {
            logging.DEBUG: self.LIGHT_CYAN + fmt + self.RESET,
            logging.INFO: self.GREEN + fmt + self.RESET,
            logging.WARNING: self.YELLOW + fmt + self.RESET,
            logging.ERROR: self.RED + fmt + self.RESET,
            logging.CRITICAL: self.BOLD_RED + fmt + self.RESET,
        }

    def format(self, record: logging.LogRecord) -> str:
        log_fmt = self.formats.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logging(debug: bool, color: bool) -> None:
    logger = logging.getLogger()
    logger.setLevel(logging.NOTSET)

    fmt = "%(levelname)8s | %(message)s"
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(
        CustomFormatter(fmt) if color else logging.Formatter(fmt)
    )

    logger.addHandler(console_handler)
