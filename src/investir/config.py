import logging
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir


@dataclass
class Config:
    strict: bool = True
    offline: bool = False
    cache_dir: Path = Path(user_cache_dir()) / "investir"
    include_fx_fees: bool = True
    log_level: int = logging.INFO
    use_colour: bool = True

    @property
    def logging_enabled(self) -> bool:
        return self.log_level != logging.CRITICAL

    def reset(self) -> None:
        Config.__init__(self)


config = Config()
