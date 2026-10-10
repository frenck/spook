"""Tests that only things shaped like a device ID get reported as one.

A device ID is a `uuid4().hex` handed out by the registry, and nothing else
can set one. Integrations are free to take a field called `device_id` meaning
their own hardware, and Home Assistant's reference extraction reads that field
out of every action's data regardless of who it belongs to.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.script import Script
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest
import yaml

from custom_components.spook.entity_filtering import (
    async_filter_known_device_ids,
    is_device_id_shaped,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr

# What the registry actually hands out, and what it never would.
_REAL = "a7ee7cb9ca6f01fd7462a7d88a17e20f"
_RFLINK = "ev1527_0ddf80_0e"


@pytest.mark.parametrize("value", [_REAL], ids=repr)
def test_these_are_shaped_like_a_device_id(value: str) -> None:
    """Exactly thirty-two lowercase hex characters, and nothing else."""
    assert is_device_id_shaped(value)


@pytest.mark.parametrize(
    "value",
    [
        _RFLINK,
        "",
        "abc",
        _REAL.upper(),
        _REAL[:-1],
        _REAL + "0",
        f" {_REAL}",
        f"{_REAL}\n",
    ],
    ids=repr,
)
def test_these_are_not(value: str) -> None:
    """Anchored at both ends, so neither padding nor a newline slips through."""
    assert not is_device_id_shaped(value)


async def test_a_real_registry_id_matches_the_shape(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The rule is only worth anything if it agrees with the registry."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "one")},
        name="A device",
    )

    assert is_device_id_shaped(device.id)


async def test_the_rflink_address_from_the_report_is_not_reported(
    hass: HomeAssistant,
) -> None:
    """RFLink takes `device_id` meaning a protocol address, not a device.

    Home Assistant's own extraction reads it out of the action data and hands
    it over as a referenced device, so this is the only thing stopping it.
    """
    sequence = yaml.safe_load(
        """
        - data:
            device_id: ev1527_0ddf80_0e
            command: 'on'
          action: rflink.send_command
        """,
    )
    script = Script(hass, sequence, "rflink", "script")

    assert _RFLINK in script.referenced_devices, (
        "core stopped handing this over, so this no longer tests anything"
    )
    assert not async_filter_known_device_ids(
        hass, device_ids=set(script.referenced_devices)
    )


async def test_a_device_that_really_is_gone_is_still_reported(
    hass: HomeAssistant,
) -> None:
    """Removing a device leaves its ID behind, still shaped like one.

    Which is the whole point: this gives up nothing worth finding.
    """
    assert async_filter_known_device_ids(hass, device_ids={_REAL}) == {_REAL}
