"""CedeStrategy -- GraphStrategy for CEDE targets (off -> flashed -> validated).

State graph::

    state_off  (root)
        |
    state_flashed  (depends: off)
        |
    state_validated  (depends: flashed)

Usage in a test::

    def test_pico(strategy, target):
        strategy.transition("validated")
        # If we get here, flash + serial banner + digest all passed.
"""

from __future__ import annotations

import logging

import attr
from labgrid.factory import target_factory
from labgrid.step import step
from labgrid.strategy import GraphStrategy

logger = logging.getLogger(__name__)


@target_factory.reg_driver
@attr.s(eq=False)
class CedeStrategy(GraphStrategy):
    """Manage a CEDE MCU target through off -> flashed -> validated."""

    bindings = {
        "flash_driver": {
            "PicotoolFlashDriver",
            "AvrdudeFlashDriver",
        },
        "validation_driver": "CedeValidationDriver",
    }

    def state_off(self):
        """Root state: ensure drivers are deactivated."""
        logger.info("CedeStrategy: entering state_off")
        try:
            self.target.deactivate(self.validation_driver)
        except Exception:
            pass
        try:
            self.target.deactivate(self.flash_driver)
        except Exception:
            pass

    @GraphStrategy.depends("off")
    def state_flashed(self):
        """Flash firmware to the target MCU."""
        logger.info("CedeStrategy: entering state_flashed")
        self.target.activate(self.flash_driver)
        self.flash_driver.flash()

    @GraphStrategy.depends("flashed")
    def state_validated(self):
        """Validate serial banner and digest after flashing."""
        logger.info("CedeStrategy: entering state_validated")
        self.target.activate(self.validation_driver)
        self.validation_driver.validate()
