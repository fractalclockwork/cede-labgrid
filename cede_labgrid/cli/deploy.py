"""Deploy firmware to a CEDE MCU target via LabGrid.

Loads the LabGrid environment, acquires drivers, and flashes the image.
Optionally validates the serial banner + digest after flashing.

Usage (called by scripts/cede-deploy.sh for pico/uno targets):
    python -m cede_labgrid.cli.deploy --env env/pico.yaml --image /path/to/fw.uf2
    python -m cede_labgrid.cli.deploy --env env/uno.yaml --image /path/to/fw.hex --validate
"""

from __future__ import annotations

import argparse
import logging
import sys

from labgrid import Environment

import cede_labgrid.drivers.picotool_flash  # noqa: F401 — register driver
import cede_labgrid.drivers.avrdude_flash  # noqa: F401
import cede_labgrid.drivers.cede_validation  # noqa: F401
import cede_labgrid.drivers.cede_reset  # noqa: F401
import cede_labgrid.strategies.cede_strategy  # noqa: F401

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, help="LabGrid env YAML (e.g. env/pico.yaml)")
    parser.add_argument("--coordinator", default="192.168.1.111:20408", help="LabGrid coordinator address")
    parser.add_argument("--image", required=True, help="Path to firmware artifact (UF2 or HEX)")
    parser.add_argument("--validate", action="store_true", help="Validate serial banner + digest after flash")
    parser.add_argument("--banner-prefix", default="", help="Override banner prefix for validation (from cede_app.yaml)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s: %(message)s",
    )

    env = Environment(args.env)
    target = env.get_target()

    from cede_labgrid.protocols.flash import FlashProtocol

    flash_driver = target.get_driver(FlashProtocol, activate=False)
    target.activate(flash_driver)

    logger.info("Flashing %s", args.image)
    flash_driver.flash(image=args.image)
    logger.info("Flash complete")

    if args.validate:
        validation_driver = target.get_driver("CedeValidationDriver", activate=False)
        if args.banner_prefix:
            validation_driver.banner_prefix = args.banner_prefix
        target.activate(validation_driver)
        logger.info("Validating serial banner + digest")
        validation_driver.validate()
        logger.info("Validation passed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
