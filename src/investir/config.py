from dataclasses import dataclass


@dataclass
class Config:
    strict: bool = True
    include_fx_fees = True


config = Config()
