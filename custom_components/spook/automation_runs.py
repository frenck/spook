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

    Listening starts when Spook does, not when a condition first asks. A
    condition sitting inside an action sequence is only built once that
    sequence runs, which is after the automation announced itself, so a
    register that started then would have missed the very run being asked
    about and would answer "no" to everything.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the register."""
        self._hass = hass
        self._by_context_id: LRU = LRU(CACHE_SIZE)
        self._unsub: CALLBACK_TYPE | None = None

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start listening, and return the way to stop."""
        if self._unsub is None:
            self._unsub = self._hass.bus.async_listen(
                EVENT_AUTOMATION_TRIGGERED, self._async_automation_ran
            )
        return self.async_stop

    @callback
    def async_stop(self) -> None:
        """Stop listening and let go of what was remembered."""
        if self._unsub is not None:
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
    """Return the shared register, starting it if this is the first ask."""
    if (runs := hass.data.get(DATA_AUTOMATION_RUNS)) is None:
        runs = AutomationRuns(hass)
        hass.data[DATA_AUTOMATION_RUNS] = runs
        runs.async_start()
    return runs


@callback
def async_setup_automation_runs(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Start remembering automation runs, and return the way to stop."""
    return async_get_automation_runs(hass).async_start()
