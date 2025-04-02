from abc import ABC, abstractmethod

from parameters import Parameter


class ChangeEvent(object):
    def __init__(self, name: Parameter, new_value, old_value=None, source=None):
        self.name = name
        self.new_value = new_value
        self.old_value = old_value
        self.source = source
        self.consumed = False

    @property
    def is_consumed(self) -> bool:
        return self.consumed


class ProjectObserver(ABC):

    @abstractmethod
    def update(self, event: ChangeEvent) -> None:
        pass
