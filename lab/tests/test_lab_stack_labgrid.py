"""Flash lab_stack firmware via LabGrid and validate serial banner + digest.

Uses the same CedeStrategy (off -> flashed -> validated) but with the
lab_stack image keys instead of the default hello_lab ones.

Requires:
    - labgrid-coordinator + exporter running
    - lab_stack firmware built (make -C lab/docker pico-build-lab-stack / uno-build-lab-stack)

Run:
    pytest --lg-env env/remote.yaml lab/tests/test_lab_stack_labgrid.py
"""

from __future__ import annotations

import pytest


@pytest.mark.labgrid
def test_pico_lab_stack_flash_and_validate(strategy, target):
    """Flash lab_stack UF2 onto Pico and validate serial banner + digest."""
    flash_driver = target.get_driver("PicotoolFlashDriver")
    validation_driver = target.get_driver("CedeValidationDriver")

    target.activate(flash_driver)
    flash_driver.flash(image="pico_uf2_lab_stack")

    target.activate(validation_driver)
    validation_driver.validate()


@pytest.mark.labgrid
def test_uno_lab_stack_flash_and_validate(strategy, target):
    """Flash lab_stack HEX onto Uno and validate serial banner + digest."""
    flash_driver = target.get_driver("AvrdudeFlashDriver")
    validation_driver = target.get_driver("CedeValidationDriver")

    target.activate(flash_driver)
    flash_driver.flash(image="uno_hex_lab_stack")

    target.activate(validation_driver)
    validation_driver.validate()
