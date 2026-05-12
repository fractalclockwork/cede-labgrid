"""Flash i2c_hello demo firmware via LabGrid and validate serial banner + digest.

Uses the same CedeStrategy (off -> flashed -> validated) as hello_lab tests,
but with i2c_hello image keys and banner prefixes configured in the env YAML.

Requires:
    - labgrid-coordinator + exporter running
    - i2c_hello firmware built (make -C lab/docker pico-build-i2c-hello / uno-build-i2c-hello)

Run:
    pytest --lg-env env/pico.yaml lab/tests/test_lab_stack_labgrid.py -k pico
    pytest --lg-env env/uno.yaml lab/tests/test_lab_stack_labgrid.py -k uno
"""

from __future__ import annotations

import pytest


@pytest.mark.labgrid
def test_pico_lab_stack_flash_and_validate(strategy, target):
    """Flash i2c_hello UF2 onto Pico and validate serial banner + digest.

    Reconfigures the flash and validation drivers to use i2c_hello image keys
    before transitioning through the strategy.
    """
    flash_driver = target.get_driver("PicotoolFlashDriver", activate=False)
    flash_driver.image = "pico_uf2_i2c_hello"

    validation_driver = target.get_driver("CedeValidationDriver", activate=False)
    validation_driver.image = "pico_uf2_i2c_hello"
    validation_driver.banner_prefix = "CEDE i2c_hello rp2 ok"

    strategy.transition("validated")


@pytest.mark.labgrid
def test_uno_lab_stack_flash_and_validate(strategy, target):
    """Flash i2c_hello HEX onto Uno and validate serial banner + digest.

    Reconfigures the flash and validation drivers to use i2c_hello image keys
    before transitioning through the strategy.
    """
    flash_driver = target.get_driver("AvrdudeFlashDriver", activate=False)
    flash_driver.image = "uno_hex_i2c_hello"

    validation_driver = target.get_driver("CedeValidationDriver", activate=False)
    validation_driver.image = "uno_hex_i2c_hello"
    validation_driver.banner_prefix = "CEDE i2c_hello ok"

    strategy.transition("validated")
