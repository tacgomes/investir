from dataclasses import dataclass
from logging import INFO


@dataclass
class Config:
    log_level: int = INFO
    use_colour: bool = True
    strict: bool = True
    offline: bool = False
    include_fx_fees: bool = True


config = Config()
