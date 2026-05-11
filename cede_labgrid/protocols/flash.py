"""FlashProtocol -- abstract interface for flashing firmware to an MCU target.

Any driver that can write firmware to a device (UF2, HEX, ELF, BIN, etc.)
should implement this protocol.  CedeStrategy binds to FlashProtocol rather
than listing concrete driver classes, making it easy to add new target types
(ESP32, STM32, etc.) without modifying the strategy.
"""

from __future__ import annotations

import abc


class FlashProtocol(abc.ABC):
    @abc.abstractmethod
    def flash(self, *, image: str | None = None) -> None:
        raise NotImplementedError
