"""Lights to adjust, and a group of them."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )

DIM = "light.dim"
BRIGHT = "light.bright"
OFF = "light.off"
PLAIN = "light.plain"
GROUP = "light.kitchen"


class OnOffLight(LightEntity):
    """A light with no dimmer, the kind a relay drives."""

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_should_poll = False

    def __init__(self, name: str, *, on: bool) -> None:
        """Initialize the light."""
        self._attr_name = name
        self._attr_unique_id = name
        self._attr_is_on = on

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn the light on."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the light off."""
        self._attr_is_on = False
        self.async_write_ha_state()


class FakeLight(LightEntity):
    """A light that remembers what it was told."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_features = LightEntityFeature.TRANSITION
    _attr_should_poll = False

    def __init__(self, name: str, brightness: int, *, on: bool) -> None:
        """Initialize the light."""
        self._attr_name = name
        self._attr_unique_id = name
        self._attr_brightness = brightness
        self._attr_is_on = on
        self.transitions: list[float | None] = []

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, at a brightness if one was given."""
        self._attr_is_on = True

        if "brightness" in kwargs:
            self._attr_brightness = kwargs["brightness"]

        self.transitions.append(kwargs.get("transition"))
        self.async_write_ha_state()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the light off."""
        self._attr_is_on = False
        self.async_write_ha_state()


async def async_set_up_lights(hass: HomeAssistant) -> None:
    """Set up three lights: one dim, one bright, one off."""

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.LIGHT])
        return True

    async def _setup_platform(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        add(
            [
                FakeLight("dim", 26, on=True),
                FakeLight("bright", 255, on=True),
                FakeLight("off", 128, on=False),
                OnOffLight("plain", on=True),
            ]
        )

    mock_integration(hass, MockModule("fake", async_setup_entry=_setup_entry))
    mock_platform(hass, "fake.config_flow")
    mock_platform(hass, "fake.light", MockPlatform(async_setup_entry=_setup_platform))

    class _Flow(ConfigFlow, domain="fake"):
        """A config flow that does nothing."""

    with mock_config_flow("fake", _Flow):
        entry = MockConfigEntry(domain="fake")
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def async_set_up_group(hass: HomeAssistant, members: list[str]) -> None:
    """Put the given lights behind a light group helper."""
    entry = MockConfigEntry(
        domain="group",
        data={},
        options={
            "group_type": "light",
            "name": "Kitchen",
            "entities": members,
            "hide_members": False,
        },
        title="Kitchen",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
