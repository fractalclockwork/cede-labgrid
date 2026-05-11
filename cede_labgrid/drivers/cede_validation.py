"""CedeValidationDriver -- validate firmware banner and digest via serial console.

Reads the expected digest from a ``.digest`` sidecar file next to the build
artifact registered in LabGrid's ``images:`` section.  Opens the serial
console (via ConsoleProtocol), optionally resets the device (DTR toggle for
Uno, post-flash reboot wait for Pico), reads the banner, and asserts the
``digest=<token>`` field matches.

This replaces the old FIRMWARE_DIGEST / CEDE_TEST_IMAGE_ID / cede_firmware_attest.py
pipeline with a single LabGrid driver.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Literal

import attr
from labgrid.driver import Driver
from labgrid.factory import target_factory
from labgrid.protocol import ConsoleProtocol
from labgrid.step import step

logger = logging.getLogger(__name__)

Role = Literal["pico", "uno"]

BANNER_PREFIXES: dict[Role, str] = {
    "pico": "CEDE hello_lab rp2 ok",
    "uno": "CEDE hello_lab ok",
}

DIGEST_RE = re.compile(r"digest=([A-Za-z0-9._-]+)", re.IGNORECASE)


def _read_digest_sidecar(image_path: str) -> str:
    """Read the one-line .digest sidecar next to the build artifact."""
    sidecar = Path(image_path + ".digest")
    if not sidecar.exists():
        raise FileNotFoundError(
            f"Digest sidecar not found: {sidecar}  "
            f"(rebuild with Docker pico-build / uno-build to generate it)"
        )
    token = sidecar.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError(f"Empty digest sidecar: {sidecar}")
    return token


@target_factory.reg_driver
@attr.s(eq=False)
class CedeValidationDriver(Driver):
    """Validate a CEDE firmware banner + digest token over serial.

    Bindings:
        console: ConsoleProtocol (SerialDriver)
    """

    bindings = {"console": ConsoleProtocol}

    role = attr.ib(validator=attr.validators.in_(("pico", "uno")))
    image = attr.ib(validator=attr.validators.instance_of(str))
    banner_timeout = attr.ib(default=8.0, validator=attr.validators.instance_of(float))

    @Driver.check_active
    @step(args=["role", "image"])
    def validate(self) -> str:
        """Read serial output and assert banner + digest match.

        Returns the captured text on success.
        Raises ``RuntimeError`` on validation failure.
        """
        image_path = self.target.env.config.get_image_path(self.image)
        expected_digest = _read_digest_sidecar(image_path)
        expected_banner = BANNER_PREFIXES[self.role]

        logger.info(
            "Validating %s: banner=%r, expected digest=%s",
            self.role, expected_banner, expected_digest,
        )

        text = self._read_serial(expected_banner)

        if expected_banner not in text:
            raise RuntimeError(
                f"Banner not found in serial output.  "
                f"Expected {expected_banner!r} within {self.banner_timeout}s.  "
                f"Got ({len(text)} chars): {text[:200]!r}"
            )

        m = DIGEST_RE.search(text)
        if not m:
            raise RuntimeError(
                f"No digest= token in serial output.  "
                f"Banner present but firmware did not emit digest=<id>.  "
                f"Capture: {text[:200]!r}"
            )

        actual_digest = m.group(1)
        if actual_digest.lower() != expected_digest.lower():
            raise RuntimeError(
                f"Digest mismatch: device has digest={actual_digest!r}, "
                f"expected digest={expected_digest!r} (from .digest sidecar)"
            )

        logger.info(
            "Validation passed: %s banner ok, digest=%s", self.role, actual_digest
        )
        return text

    def _read_serial(self, expect: str) -> str:
        """Read from the console until *expect* is seen or timeout expires."""
        buf = b""
        expect_b = expect.encode("utf-8")
        deadline = time.monotonic() + self.banner_timeout

        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            chunk = self.console.read(size=4096, timeout=min(remaining, 0.5))
            if chunk:
                buf += chunk
            if expect_b in buf:
                break

        return buf.decode("utf-8", errors="replace")
