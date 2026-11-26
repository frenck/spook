"""Spook - Your homie. Knowing when `customize:` was read again.

`homeassistant.reload_core_config` reads the `homeassistant:` section again,
`customize:` included. `homeassistant.reload_all` calls it too, as a service
of its own, so following that one call covers both. It sends no word when it
is done: the customizations are simply swapped for new ones. The service being called is too early to
look, as it still has the whole configuration to read and validate, which
takes seconds on a large one.

So the customizations themselves are watched for a while after such a call,
until they are new ones.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_RELOAD_CORE_CONFIG,
)
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import callback
from homeassistant.core_config import DATA_CUSTOMIZE
from homeassistant.helpers.event import async_call_later

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime

    from homeassistant.core import Event, HomeAssistant

# How often to check whether the customizations were read again, and how many
# times before giving up: a reload that failed keeps the old ones for good.
_CHECK_EVERY = timedelta(seconds=1)
_CHECKS = 60


class _CustomizeWatch:
    """Watching the customizations for one follower, across reloads.

    Two reloads can be under way at once, and both start from the same
    customizations. So the watch is shared: it counts the reloads still
    reading, takes every new set of customizations as the one to compare
    with next, and every call starts the time it is given over.
    """

    def __init__(self, hass: HomeAssistant, action: Callable[[], None]) -> None:
        """Initialize the watch."""
        self._hass = hass
        self._action = action
        self._before: object | None = None
        self._reading = 0
        self._checks_left = 0
        self._cancel: Callable[[], None] | None = None

    @callback
    def async_reload_called(self, _: Event) -> None:
        """Start watching, or keep watching longer, for a reload just called."""
        if not self._reading:
            self._before = self._hass.data.get(DATA_CUSTOMIZE)
        self._reading += 1
        self._checks_left = _CHECKS

        if self._cancel is None:
            self._cancel = async_call_later(self._hass, _CHECK_EVERY, self._check)

    @callback
    def _check(self, _: datetime) -> None:
        """Follow up on new customizations, and watch on while reloads read."""
        self._cancel = None

        if (current := self._hass.data.get(DATA_CUSTOMIZE)) is not self._before:
            self._before = current
            self._reading -= 1
            self._action()

        self._checks_left -= 1
        if self._reading > 0 and self._checks_left > 0:
            self._cancel = async_call_later(self._hass, _CHECK_EVERY, self._check)
            return

        # Done, or given up on: a reload that failed keeps the old ones.
        self._reading = 0

    @callback
    def async_stop(self) -> None:
        """Stop watching, dropping a check under way."""
        if self._cancel is not None:
            self._cancel()
            self._cancel = None
        self._reading = 0


@callback
def async_follow_customize_reloads(
    hass: HomeAssistant, action: Callable[[], None]
) -> Callable[[], None]:
    """Call ``action`` every time `customize:` was read again.

    Returns what stops following, a wait under way included.
    """
    watch = _CustomizeWatch(hass, action)

    @callback
    def _reads_customize(event_data: Mapping[str, Any]) -> bool:
        """Return whether a service call reads `customize:` again."""
        return (
            event_data.get("domain") == HOMEASSISTANT_DOMAIN
            and event_data.get("service") == SERVICE_RELOAD_CORE_CONFIG
        )

    stop_listening = hass.bus.async_listen(
        EVENT_CALL_SERVICE, watch.async_reload_called, event_filter=_reads_customize
    )

    @callback
    def _stop() -> None:
        stop_listening()
        watch.async_stop()

    return _stop
