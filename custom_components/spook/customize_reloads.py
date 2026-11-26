"""Spook - Your homie. Knowing when `customize:` was read again.

`homeassistant.reload_core_config` reads the `homeassistant:` section again,
`customize:` included, and `homeassistant.reload_all` does that along with
everything else. Neither sends a word when it is done: the customizations
are simply swapped for new ones. The service being called is too early to
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
    SERVICE_RELOAD_ALL,
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

_READING_CUSTOMIZE = frozenset({SERVICE_RELOAD_CORE_CONFIG, SERVICE_RELOAD_ALL})


@callback
def async_follow_customize_reloads(
    hass: HomeAssistant, action: Callable[[], None]
) -> Callable[[], None]:
    """Call ``action`` every time `customize:` was read again.

    Returns what stops following, waits under way included.
    """
    waiting: set[Callable[[], None]] = set()

    @callback
    def _reads_customize(event_data: Mapping[str, Any]) -> bool:
        """Return whether a service call reads `customize:` again."""
        return (
            event_data.get("domain") == HOMEASSISTANT_DOMAIN
            and event_data.get("service") in _READING_CUSTOMIZE
        )

    @callback
    def _wait_for_new_ones(_: Event) -> None:
        """Watch the customizations until they are new ones, or give up."""
        before = hass.data.get(DATA_CUSTOMIZE)
        checks_left = _CHECKS
        cancel: Callable[[], None] | None = None

        @callback
        def _check(_: datetime) -> None:
            nonlocal cancel, checks_left
            waiting.discard(cancel)  # type: ignore[arg-type]

            if hass.data.get(DATA_CUSTOMIZE) is not before:
                action()
                return

            checks_left -= 1
            if checks_left:
                cancel = async_call_later(hass, _CHECK_EVERY, _check)
                waiting.add(cancel)

        cancel = async_call_later(hass, _CHECK_EVERY, _check)
        waiting.add(cancel)

    stop_listening = hass.bus.async_listen(
        EVENT_CALL_SERVICE, _wait_for_new_ones, event_filter=_reads_customize
    )

    @callback
    def _stop() -> None:
        stop_listening()
        for cancel in list(waiting):
            cancel()
        waiting.clear()

    return _stop
