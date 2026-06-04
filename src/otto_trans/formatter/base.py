from abc import ABC, abstractmethod

class BaseFormatter(ABC):
    @abstractmethod
    def format(self, data):
        ...