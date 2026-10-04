"""Tests for the media player increase and decrease volume actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.media_player.services.decrease_volume import (
    SpookService as DecreaseService,
)
from custom_components.spook.ectoplasms.media_player.services.increase_volume import (
    SpookService as IncreaseService,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )


class FakeSpeaker(MediaPlayerEntity):
    """A speaker that remembers how loud it was told to be."""

    _attr_should_poll = False
    _attr_state = MediaPlayerState.PLAYING
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(self, name: str, volume: float | None) -> None:
        """Initialize the speaker."""
        self._attr_name = name
        self._attr_unique_id = name
        self._attr_volume_level = volume
        self.told: list[float] = []

    async def async_set_volume_level(self, volume: float) -> None:
        """Take the new volume."""
        self.told.append(volume)
        self._attr_volume_level = volume
        self.async_write_ha_state()


class FakeRadio(FakeSpeaker):
    """A radio with only its own up and down buttons, no level to set."""

    _attr_supported_features = MediaPlayerEntityFeature.VOLUME_STEP


async def _setup(
    hass: HomeAssistant, *players: MediaPlayerEntity, parallel_updates: int = 0
) -> None:
    """Set up these media players and both actions."""
    assert await async_setup_component(hass, "homeassistant", {})

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(
            entry, [Platform.MEDIA_PLAYER]
        )
        return True

    async def _setup_platform(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        add(list(players))

    mock_integration(hass, MockModule("fake", async_setup_entry=_setup_entry))
    mock_platform(hass, "fake.config_flow")
    platform = MockPlatform(async_setup_entry=_setup_platform)
    if parallel_updates:
        platform.PARALLEL_UPDATES = parallel_updates  # type: ignore[attr-defined]
    mock_platform(hass, "fake.media_player", platform)

    class _Flow(ConfigFlow, domain="fake"):
        """A config flow that does nothing."""

    with mock_config_flow("fake", _Flow):
        entry = MockConfigEntry(domain="fake")
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    IncreaseService(hass).async_register()
    DecreaseService(hass).async_register()
    await hass.async_block_till_done()


async def _step(hass: HomeAssistant, service: str, entity_id: str, **data: Any) -> None:
    """Step a media player."""
    await hass.services.async_call(
        "media_player", service, {"entity_id": entity_id, **data}, blocking=True
    )


async def test_the_volume_moves_by_the_step_asked_for(hass: HomeAssistant) -> None:
    """Test the volume goes up and down by exactly the given percentage."""
    kitchen = FakeSpeaker("kitchen", 0.4)
    await _setup(hass, kitchen)

    await _step(hass, "increase_volume", "media_player.kitchen", step=5)
    await _step(hass, "decrease_volume", "media_player.kitchen", step=30)

    assert kitchen.told == [0.45, 0.15]


async def test_silent_and_full_are_the_limits(hass: HomeAssistant) -> None:
    """Test a step stops at full and at silent, and one there does nothing."""
    loud = FakeSpeaker("loud", 0.95)
    quiet = FakeSpeaker("quiet", 0.0)
    await _setup(hass, loud, quiet)

    await _step(hass, "increase_volume", "media_player.loud", step=10)
    await _step(hass, "decrease_volume", "media_player.quiet", step=10)

    assert loud.told == [1.0]
    assert not quiet.told


async def test_the_step_is_required(hass: HomeAssistant) -> None:
    """Test a step has to be given, or it would be `volume_up` again."""
    await _setup(hass, FakeSpeaker("kitchen", 0.4))

    with pytest.raises(vol.Invalid):
        await _step(hass, "increase_volume", "media_player.kitchen")


async def test_without_a_volume_nothing_happens(hass: HomeAssistant) -> None:
    """Test a player that does not report its volume, often when off."""
    off = FakeSpeaker("off", None)
    await _setup(hass, off)

    await _step(hass, "increase_volume", "media_player.off", step=10)

    assert not off.told


async def test_a_player_without_a_volume_level_refuses(hass: HomeAssistant) -> None:
    """Test a player that only has up and down buttons says so."""
    await _setup(hass, FakeRadio("radio", 0.4))

    with pytest.raises(ServiceNotSupported):
        await _step(hass, "increase_volume", "media_player.radio", step=10)


async def test_one_at_a_time_platforms_are_not_held_up(hass: HomeAssistant) -> None:
    """Test a platform that does one call at a time still gets the step."""
    kitchen = FakeSpeaker("kitchen", 0.4)
    await _setup(hass, kitchen, parallel_updates=1)

    async with asyncio.timeout(5):
        await _step(hass, "increase_volume", "media_player.kitchen", step=10)

    assert kitchen.told == [0.5]
