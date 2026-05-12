"""Hardware flash + validate test for {{APP_NAME}}.

Requires:
    - labgrid coordinator + exporter running
    - Firmware built (make build or make docker-build)

Run:
    pytest --lg-env env/your-env.yaml tests/
"""

from __future__ import annotations

import pytest


@pytest.mark.labgrid
def test_flash_and_validate(strategy, target):
    """Flash firmware and validate serial banner + digest."""
    strategy.transition("validated")
