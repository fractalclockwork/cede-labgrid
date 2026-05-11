"""CedeValidationDriver -- validate firmware banner and digest via serial console.

Reads the expected digest from a ``.digest`` sidecar file next to the build
artifact registered in LabGrid's ``images:`` section.  Uses ConsoleExpectMixin
(pexpect-style matching with --lg-log integration) to wait for the banner and
assert the ``digest=<token>`` field matches.

This replaces the old FIRMWARE_DIGEST / CEDE_TEST_IMAGE_ID / cede_firmware_attest.py
pipeline with a single LabGrid driver.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

import attr
from labgrid.driver import Driver
from labgrid.driver.consoleexpectmixin import ConsoleExpectMixin
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
class CedeValidationDriver(ConsoleExpectMixin, Driver):
    """Validate a CEDE firmware banner + digest token over serial.

    Uses ConsoleExpectMixin for pexpect-style matching and --lg-log integration.

    Bindings:
        console: ConsoleProtocol (SerialDriver)
    """

    bindings = {"console": ConsoleProtocol}

    role = attr.ib(validator=attr.validators.in_(("pico", "uno")))
    image = attr.ib(validator=attr.validators.instance_of(str))
    banner_timeout = attr.ib(default=8.0, validator=attr.validators.instance_of(float))
    txdelay = attr.ib(default=0.0, validator=attr.validators.instance_of(float))

    def _read(self, size: int = 1, timeout: float = 0.0, max_size: int | None = None) -> bytes:
        return self.console.read(size=size, timeout=timeout, max_size=max_size)

    def _write(self, data: bytes) -> int:
        return self.console.write(data)

    @Driver.check_active
    @step()
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

        banner_pattern = re.escape(expected_banner) + r".*?digest=([A-Za-z0-9._-]+)[\s\r\n]"
        try:
            _, before, match, after = self.expect(banner_pattern, timeout=self.banner_timeout)
        except TIMEOUT:
            collected = self._expect.before or b""
            text = collected.decode("utf-8", errors="replace") if isinstance(collected, bytes) else str(collected)
            raise RuntimeError(
                f"Banner not found in serial output.  "
                f"Expected {expected_banner!r} within {self.banner_timeout}s.  "
                f"Got ({len(text)} chars): {text[:200]!r}"
            ) from None

        raw = match.group(1) if hasattr(match, "group") else ""
        actual_digest = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        if not actual_digest:
            text = _decode_expect(before) + _decode_expect(match) + _decode_expect(after)
            raise RuntimeError(
                f"No digest= token in serial output.  "
                f"Banner present but firmware did not emit digest=<id>.  "
                f"Capture: {text[:200]!r}"
            )

        a, e = actual_digest.lower().strip(), expected_digest.lower().strip()
        if a != e:
            raise RuntimeError(
                f"Digest mismatch: device has digest={actual_digest!r}, "
                f"expected digest={expected_digest!r} (from .digest sidecar)"
            )
        logger.info("Digest validated: %s", a)

        logger.info(
            "Validation passed: %s banner ok, digest=%s", self.role, actual_digest
        )
        text = _decode_expect(before) + _decode_expect(match) + _decode_expect(after)
        return text


def _decode_expect(value: object) -> str:
    """Decode bytes/match/str from pexpect into a string."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "group"):
        raw = value.group(0)
        return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    return str(value) if value else ""


try:
    from pexpect import TIMEOUT
except ImportError:
    TIMEOUT = type("TIMEOUT", (Exception,), {})
