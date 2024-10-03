import logging
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_dir


@dataclass
class Config:
    strict: bool = True
    offline: bool = False
    cache_file: Path = Path(user_cache_dir()) / "investir" / "securities.yaml"
    include_fx_fees: bool = True
    log_level: int = logging.INFO
    use_colour: bool = True

    def reset(self) -> None:
        Config.__init__(self)


config = Config()
