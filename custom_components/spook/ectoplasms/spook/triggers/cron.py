"""Spook - Your homie."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from cronsim import CronSim, CronSimError
import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.trigger import Trigger
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
    from homeassistant.helpers.trigger import (
        TriggerActionRunner,
        TriggerConfig,
        TriggerNotTriggeredReporter,
    )
    from homeassistant.helpers.typing import ConfigType

CONF_SCHEDULE = "schedule"

_CRON_FIELDS = 5


def _cron_schedule(value: Any) -> str:
    """Validate a crontab expression, and say what is wrong with it if not."""
    schedule = str(value)

    # cronsim also takes a six-field form, where the leading field is seconds.
    # That would hand out triggers firing every second, which is neither what
    # this documents nor something to run an automation off. Five fields only.
    if len(schedule.split()) != _CRON_FIELDS:
        message = (
            f"Invalid crontab expression '{schedule}': expected "
            f"{_CRON_FIELDS} fields (minute, hour, day of month, month, "
            "day of week)"
        )
        raise vol.Invalid(message)

    try:
        # Any date will do here; this only asks whether the expression parses.
        CronSim(schedule, datetime(2020, 1, 1))  # noqa: DTZ001
    except CronSimError as err:
        message = f"Invalid crontab expression '{schedule}': {err}"
        raise vol.Invalid(message) from err

    return schedule


_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_SCHEDULE): _cron_schedule,
        },
    }
)


class SpookTrigger(Trigger):
    """Spook trigger that fires on a crontab schedule.

    Home Assistant's time triggers cover a time of day and a time pattern,
    which between them cannot say "every weekday at seven" or "the last
    Friday of the month". A crontab expression can, in one line, and people
    coming from cron already know how to write it.
    """

    trigger = "cron"

    _schedule: str

    @classmethod
    async def async_validate_config(
        cls,
        hass: HomeAssistant,  # noqa: ARG003
        config: ConfigType,
    ) -> ConfigType:
        """Validate the trigger config."""
        return _TRIGGER_SCHEMA(config)  # type: ignore[no-any-return]

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        options: dict[str, Any] = config.options or {}
        self._schedule = options[CONF_SCHEDULE]

    def _next(self, after: datetime) -> datetime | None:
        """Return the next time this schedule comes round, if it ever does.

        cronsim 2.7 refuses an impossible date at parse time rather than
        accepting it and never firing, so in practice this returns a time.
        The guard stays because exhausting an iterator is a thing iterators
        do, and a trigger that raises instead of going quiet would take the
        automation with it.
        """
        try:
            return next(CronSim(self._schedule, after))
        except StopIteration:
            return None

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,  # noqa: ARG002
    ) -> CALLBACK_TYPE:
        """Attach the trigger to an action runner."""
        unsub: CALLBACK_TYPE | None = None

        @callback
        def schedule_next(after: datetime) -> None:
            """Wait for the next time the schedule comes round."""
            nonlocal unsub
            if (upcoming := self._next(after)) is None:
                return
            unsub = async_track_point_in_time(self._hass, fire, upcoming)

        @callback
        def fire(_scheduled: datetime) -> None:
            """Run the action, then line up the one after it."""
            nonlocal unsub
            unsub = None

            # Ask what time it is rather than trusting the time handed over:
            # that one is the time this run was scheduled for, which stops
            # being the current time once the machine has been asleep.
            # Continuing from it would then work through every minute that was
            # missed, one automation run each. Core's own time trigger fetches
            # the time again for the same reason.
            now = dt_util.now()

            schedule_next(now)
            run_action(
                {"schedule": self._schedule, "now": now},
                f"cron schedule {self._schedule}",
            )

        # A local, timezone-aware time: cronsim needs the zone to get daylight
        # saving right.
        schedule_next(dt_util.now())

        @callback
        def unattach() -> None:
            """Stop waiting."""
            nonlocal unsub
            if unsub is not None:
                unsub()
                unsub = None

        return unattach
