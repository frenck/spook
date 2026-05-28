"""Tests for Spook listener helpers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import callback

from custom_components.spook.listeners import async_listen_once_tracked

if TYPE_CHECKING:
    import pytest

    from homeassistant.core import Event, HomeAssistant


async def test_tracked_one_time_listener_unsub_after_fire_is_noop(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test tracked one-time listener unsubscribe is a no-op after firing."""
    calls = 0

    @callback
    def _listener(_: Event) -> None:
        """Handle the event."""
        nonlocal calls
        calls += 1

    unsubscribe = async_listen_once_tracked(
        hass, EVENT_HOMEASSISTANT_STARTED, _listener
    )

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    with caplog.at_level(logging.ERROR, logger="homeassistant.core"):
        unsubscribe()

    assert calls == 1
    assert "Unable to remove unknown job listener" not in caplog.text


async def test_tracked_one_time_listener_unsub_is_idempotent(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test tracked one-time listener unsubscribe can be called repeatedly."""
    calls = 0

    @callback
    def _listener(_: Event) -> None:
        """Handle the event."""
        nonlocal calls
        calls += 1

    unsubscribe = async_listen_once_tracked(
        hass, EVENT_HOMEASSISTANT_STARTED, _listener
    )

    with caplog.at_level(logging.ERROR, logger="homeassistant.core"):
        unsubscribe()
        unsubscribe()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert calls == 0
    assert "Unable to remove unknown job listener" not in caplog.text
