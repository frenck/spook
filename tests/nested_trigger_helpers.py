"""Helpers for the watchers that attach nested triggers.

Every Spook trigger built on other triggers has the same window in it:
stopping is synchronous and attaching is not, so a stop can land while
`async_initialize_triggers` is still inside an await. Whatever that takes
afterwards has nobody left to hand it back to.

Three watchers carry a test for it, all doing the same dance, so the dance
lives here.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Protocol
from unittest.mock import patch

from homeassistant.helpers import trigger as trigger_helper

from custom_components.spook import trigger_nesting

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant


class _Watcher(Protocol):
    """What this needs of a watcher: a way to start it and a way to stop it."""

    async def async_start(self) -> CALLBACK_TYPE:
        """Attach whatever it listens to."""

    def async_stop(self) -> None:
        """Let go of all of it."""


async def async_stop_while_attaching(
    hass: HomeAssistant,
    watcher: _Watcher,
    *,
    holding: str,
) -> None:
    """Stop a watcher while one of its attaches is suspended.

    `holding` is matched against the name the watcher gives the attach it is
    waiting on, which is what picks out which of several to hold open.

    Overlapped on purpose. Awaiting `async_start` and only then stopping never
    puts the two at the same moment, and a version of the watchdog's test that
    did exactly that passed against a watchdog which leaked its listener.
    Review caught it, which is why this shape is the one all three use.
    """
    real = trigger_helper.async_initialize_triggers
    hold = asyncio.Event()
    attaching = asyncio.Event()

    async def _suspending(*args: Any, **kwargs: Any):  # noqa: ANN202
        if holding in args[4]:
            attaching.set()
            await hold.wait()
        return await real(*args, **kwargs)

    with patch.object(
        trigger_nesting.trigger_helper, "async_initialize_triggers", _suspending
    ):
        starting = hass.async_create_task(watcher.async_start())
        async with asyncio.timeout(5):
            await attaching.wait()

        watcher.async_stop()

        hold.set()
        async with asyncio.timeout(5):
            await starting
        await hass.async_block_till_done()
