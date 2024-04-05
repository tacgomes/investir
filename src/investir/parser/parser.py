from abc import ABC, abstractmethod

from ..transaction import Transaction


class Parser(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def can_parse(self) -> bool:
        pass

    @abstractmethod
    def parse(self) -> list[Transaction]:
        pass
