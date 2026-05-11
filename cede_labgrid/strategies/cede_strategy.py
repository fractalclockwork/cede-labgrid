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

from cede_labgrid.protocols.flash import FlashProtocol

logger = logging.getLogger(__name__)


@target_factory.reg_driver
@attr.s(eq=False)
class CedeStrategy(GraphStrategy):
    """Manage a CEDE MCU target through off -> flashed -> validated."""

    bindings = {
        "flash_driver": FlashProtocol,
        "validation_driver": "CedeValidationDriver",
        "reset_driver": {"CedeResetDriver", None},
    }

    def state_off(self):
        """Root state: reset the target and deactivate drivers."""
        logger.info("CedeStrategy: entering state_off")
        try:
            self.target.deactivate(self.validation_driver)
        except Exception:
            pass
        try:
            self.target.deactivate(self.flash_driver)
        except Exception:
            pass
        if self.reset_driver is not None:
            try:
                self.target.activate(self.reset_driver)
                self.reset_driver.reset()
            except Exception:
                logger.debug("Reset driver failed (non-fatal)", exc_info=True)

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
