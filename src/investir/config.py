from dataclasses import dataclass
from logging import INFO
from pathlib import Path

from platformdirs import user_cache_dir


@dataclass
class Config:
    log_level: int = INFO
    use_colour: bool = True
    strict: bool = True
    offline: bool = False
    cache_file: Path = Path(user_cache_dir()) / "investir" / "securities.yaml"
    include_fx_fees: bool = True


config = Config()
