"""Tests for the Spook cloud switches."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

REPOSITORY_ROOT = Path(__file__).parents[3]


def test_loading_the_platform_leaves_the_cloud_integration_alone() -> None:
    """Test importing the cloud switches does not import the cloud integration.

    It is imported for every house at startup, on the single import thread,
    and the cloud integration brings Alexa, Google Assistant and camera with
    it. A house that does not use the cloud should not pay for that. #1898.

    In a fresh interpreter, because this one has long imported it for others.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys\n"
                "import custom_components.spook.ectoplasms.cloud.switch\n"
                "print('homeassistant.components.cloud' in sys.modules)\n"
            ),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
