from dataclasses import dataclass


@dataclass
class Config:
    strict: bool = True


config = Config()
