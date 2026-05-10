#!/usr/bin/env python3
"""Run hello_gateway (aarch64) on this machine and verify stdout banner + digest=.

Expect this script under the sparse flash-deps tree (**sync_gateway_flash_deps.sh**, e.g. **~/cede**).
The Dev-Host **scp**s the binary to **/tmp** — the gateway does not need a full CEDE checkout.
On success prints expected-digest: and digest-banner: before any stderr from the child.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from cede_firmware_attest import attestation_failure_reason, digest_banner_line, expected_digest_value


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "executable",
        help="path to hello_gateway binary (e.g. /tmp/cede_hello_gateway)",
    )
    p.add_argument("--digest", default="", help="if set, digest= token must match this string")
    args = p.parse_args()

    digest_must = expected_digest_value(args.digest)
    try:
        proc = subprocess.run(
            [args.executable],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except OSError as e:
        extra = ""
        if getattr(e, "errno", None) == 8 or "Exec format error" in str(e):
            extra = " (binary not executable for this CPU — expected aarch64 from gateway-native-hello-build)"
        print(f"validate: fail (could not run {args.executable!r}: {e}{extra})", file=sys.stderr)
        return 2

    out = (proc.stdout or b"") + (proc.stderr or b"")
    bline = digest_banner_line(out, "gateway")
    if digest_must:
        print(f"expected-digest: {digest_must}")
    if bline:
        print(f"digest-banner: {bline}")

    reason = attestation_failure_reason(out, "gateway", digest_must)
    if reason:
        print(f"validate: fail ({reason})", file=sys.stderr)
        if proc.returncode != 0:
            print(f"validate: note: process exited {proc.returncode}", file=sys.stderr)
        return 3
    if proc.returncode != 0:
        print(f"validate: fail (process exited {proc.returncode})", file=sys.stderr)
        return proc.returncode or 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
