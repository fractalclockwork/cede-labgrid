"""Shared firmware attestation: banner prefix + digest= (hello_lab USB or hello_gateway stdout)."""

from __future__ import annotations

import os
import re
from typing import Literal

Role = Literal["pico", "uno", "gateway"]

BANNER_PICO_PREFIX = b"CEDE hello_lab rp2 ok"
BANNER_UNO_PREFIX = b"CEDE hello_lab ok"
BANNER_GATEWAY_PREFIX = b"CEDE hello_gateway ok"
# digest=<token> — token from gen_cede_image_id / CMake (git short, CEDE_IMAGE_ID, nogit, unknown)
DIGEST_RE = re.compile(rb"digest=([A-Za-z0-9._-]+)", re.IGNORECASE)


def digest_token(buf: bytes) -> bytes | None:
    m = DIGEST_RE.search(buf)
    return m.group(1) if m else None


def banner_prefix_ok(buf: bytes, role: Role) -> bool:
    if role == "pico":
        p = BANNER_PICO_PREFIX
    elif role == "uno":
        p = BANNER_UNO_PREFIX
    else:
        p = BANNER_GATEWAY_PREFIX
    return p in buf


def digest_banner_line(buf: bytes, role: Role) -> str | None:
    """First line containing the role banner prefix and digest= (for human-readable logs)."""
    if role == "uno":
        prefix = "CEDE hello_lab ok"
    elif role == "pico":
        prefix = "CEDE hello_lab rp2 ok"
    else:
        prefix = "CEDE hello_gateway ok"
    for raw in buf.splitlines():
        line = raw.decode("utf-8", errors="replace").strip()
        low = line.lower()
        if prefix.lower() in low and "digest=" in low:
            return line
    return None


def expected_digest_value(cli_digest: str) -> str:
    """CLI --digest wins, else CEDE_EXPECT_DIGEST env."""
    d = (cli_digest or "").strip()
    if d:
        return d
    return (os.environ.get("CEDE_EXPECT_DIGEST") or "").strip()


def digest_mismatch_message(buf: bytes, digest_must_equal: str) -> str | None:
    """If digest token exists and does not match digest_must_equal, return error string; else None."""
    if not digest_must_equal:
        return None
    tok = digest_token(buf)
    if not tok:
        return None
    if tok.lower() != digest_must_equal.lower().encode("ascii"):
        return (
            f"digest mismatch: device has digest={tok.decode('ascii', errors='replace')!r}, "
            f"expected digest={digest_must_equal!r}"
        )
    return None


def attestation_failure_reason(buf: bytes, role: Role, digest_must_equal: str) -> str | None:
    """
    Return None if attestation passes, else a short error string.
    Always requires the role banner prefix and a digest= token.
    If digest_must_equal is non-empty, the token must match (case-insensitive).
    """
    if not banner_prefix_ok(buf, role):
        if role == "gateway":
            return "missing hello_gateway banner line on stdout (wrong binary or empty output)"
        return "missing hello_lab serial banner (wrong firmware or no USB banner yet)"
    tok = digest_token(buf)
    if not tok:
        if role == "gateway":
            return "stdout must include digest=<id> (rebuild hello_gateway with gen_cede_gateway_digest.sh)"
        return "banner must include digest=<id> (reflash hello_lab built with digest support)"
    if digest_must_equal:
        if tok.lower() != digest_must_equal.lower().encode("ascii"):
            return (
                f"digest mismatch: device has digest={tok.decode('ascii', errors='replace')!r}, "
                f"expected digest={digest_must_equal!r}"
            )
    return None
