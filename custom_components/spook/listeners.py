"""Listener helpers for Spook."""

from __future__ import annotations

from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, Any, cast

from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from homeassistant.util.event_type import EventType


def async_listen_once_tracked(
    hass: HomeAssistant,
    event_type: EventType[Any] | str,
    listener: Callable[[Event[Any]], Coroutine[Any, Any, None] | None],
) -> CALLBACK_TYPE:
    """Listen once for an event and return an idempotent unsubscribe callback."""
    remove: CALLBACK_TYPE | None = None

    if iscoroutinefunction(listener):

        async def _async_event_listener(event: Event[Any]) -> None:
            """Handle the one-time event."""
            nonlocal remove
            remove = None
            await listener(event)

        remove = hass.bus.async_listen_once(event_type, _async_event_listener)

    else:

        @callback
        def _event_listener(event: Event[Any]) -> None:
            """Handle the one-time event."""
            nonlocal remove
            remove = None
            cast("Callable[[Event[Any]], None]", listener)(event)

        remove = hass.bus.async_listen_once(event_type, _event_listener)

    @callback
    def _remove_listener() -> None:
        """Remove the listener if it has not fired yet."""
        nonlocal remove
        if remove is None:
            return
        _remove = remove
        remove = None
        _remove()

    return _remove_listener
