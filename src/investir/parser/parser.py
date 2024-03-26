from abc import ABC, abstractmethod


class Parser(ABC):
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def can_parse(self):
        pass

    @abstractmethod
    def parse(self):
        pass
