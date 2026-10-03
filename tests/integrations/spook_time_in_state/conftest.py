"""Test fixtures for the Spook time in state integration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import custom_components
from custom_components.spook.integrations import spook_time_in_state
from custom_components.spook.integrations.spook_time_in_state.const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def link_spook_time_in_state_sub_integration(hass: HomeAssistant) -> None:
    """Link the Spook time in state sub-integration into the test config dir."""
    custom_components_dir = Path(hass.config.config_dir) / "custom_components"
    custom_components_dir.mkdir(exist_ok=True)
    if str(custom_components_dir) not in custom_components.__path__:
        custom_components.__path__.append(str(custom_components_dir))

    link = custom_components_dir / DOMAIN
    target = Path(spook_time_in_state.__file__).parent
    if link.is_symlink():
        if link.readlink() == target:
            return
        link.unlink()
    elif link.exists():
        return

    link.symlink_to(
        target,
        target_is_directory=True,
    )
