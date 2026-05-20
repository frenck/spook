"""Shared fixtures for the Spook test suite."""

# pylint: disable=unused-argument
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,  # noqa: ARG001
) -> None:
    """Enable loading of the Spook custom integration for every test."""
    return
