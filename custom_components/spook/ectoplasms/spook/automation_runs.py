"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lru import LRU

from homeassistant.components.automation import EVENT_AUTOMATION_TRIGGERED
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

DATA_AUTOMATION_RUNS: HassKey[AutomationRuns] = HassKey("spook_automation_runs")

# Every automation run adds an entry, and a busy house has plenty of them. The
# answer is only ever wanted for a run that has just happened, a moment or two
# ago at most, so the oldest can be dropped without losing anything anybody
# would ask about.
CACHE_SIZE = 512


class AutomationRuns:
    """Remembers which automation started the run behind a context.

    Home Assistant does not resolve a context back to whatever created it, so
    this listens for automations announcing themselves and keeps the mapping.
    The context an automation runs under is the same one its actions write
    with, and it survives a script in between, so an automation reacting to
    that change finds it on `trigger.to_state.context`.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the register."""
        self._hass = hass
        self._by_context_id: LRU = LRU(CACHE_SIZE)
        self._unsub: CALLBACK_TYPE | None = None
        self._users = 0

    @callback
    def async_acquire(self) -> None:
        """Start listening, if nobody was listening yet."""
        self._users += 1
        if self._unsub is None:
            self._unsub = self._hass.bus.async_listen(
                EVENT_AUTOMATION_TRIGGERED, self._async_automation_ran
            )

    @callback
    def async_release(self) -> None:
        """Stop listening once the last user is done."""
        self._users = max(0, self._users - 1)
        if self._users or self._unsub is None:
            return

        self._unsub()
        self._unsub = None
        self._by_context_id.clear()

    @callback
    def async_which(self, context_id: str) -> str | None:
        """Return the automation that ran under this context, if it is known."""
        return self._by_context_id.get(context_id)  # type: ignore[no-any-return]

    @callback
    def _async_automation_ran(self, event: Event) -> None:
        """Note the context an automation is running under."""
        if entity_id := event.data.get(ATTR_ENTITY_ID):
            self._by_context_id[event.context.id] = entity_id


@callback
def async_get_automation_runs(hass: HomeAssistant) -> AutomationRuns:
    """Return the shared register, making it if this is the first ask."""
    if (runs := hass.data.get(DATA_AUTOMATION_RUNS)) is None:
        runs = AutomationRuns(hass)
        hass.data[DATA_AUTOMATION_RUNS] = runs
    return runs
