#!/usr/bin/env python3
"""
"""

from abc import ABC, abstractmethod


class SpeedControlSetter(ABC):
    """
    abstract base class for speed control setters
    """

    @abstractmethod
    def is_valid_step(self, value: int) -> bool:
        ...

    @abstractmethod
    def get_steps(self) -> list[int]:
        ...

    @abstractmethod
    def convert_percent2step(self, percent: int) -> int | None:
        ...

    @abstractmethod
    def convert_step2percent(self, step: int) -> int:
        ...

    @abstractmethod
    def convert_rpm2step(self, rpm: int) -> int | None:
        ...

    @abstractmethod
    def convert_step2rpm(self, step: int) -> int | None:
        ...
