"""Spook - Your homie."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from cronsim import CronSim, CronSimError
import voluptuous as vol

from homeassistant.const import CONF_OPTIONS, EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.trigger import Trigger
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant
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
        # Advance it once rather than only building it. Parsing accepts some
        # expressions that can never come round, such as a day of the month
        # and a day of the week that never fall together, and those only show
        # themselves when the iterator runs dry. Any date will do as a start.
        next(CronSim(schedule, datetime(2020, 1, 1)))  # noqa: DTZ001
    except CronSimError as err:
        message = f"Invalid crontab expression '{schedule}': {err}"
        raise vol.Invalid(message) from err
    except StopIteration:
        message = f"Crontab expression '{schedule}' never comes round"
        raise vol.Invalid(message) from None

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

        Validation already turned away the expressions that never come round,
        so in practice this returns a time. The guard stays because exhausting
        an iterator is a thing iterators do, and a trigger that raises rather
        than going quiet would take the automation down with it.
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
        time_zone = self._hass.config.time_zone

        @callback
        def schedule_next(after: datetime) -> None:
            """Wait for the next time the schedule comes round."""
            nonlocal unsub
            if (upcoming := self._next(after)) is None:
                return
            unsub = async_track_point_in_time(self._hass, fire, upcoming)

        @callback
        def stop_waiting() -> None:
            """Drop the pending wait, if there is one."""
            nonlocal unsub
            if unsub is not None:
                unsub()
                unsub = None

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

        @callback
        def core_config_changed(_event: Event) -> None:
            """Work the pending wait out again when the time zone changes.

            The wait is a single absolute instant, worked out in whichever
            zone was configured at the time. Change the zone and that instant
            still points at the old zone's wall clock, so one run lands at the
            wrong hour. Core's utility meter runs on cronsim too and rebuilds
            its schedule here for the same reason.
            """
            nonlocal time_zone
            if self._hass.config.time_zone == time_zone:
                return

            time_zone = self._hass.config.time_zone
            stop_waiting()
            schedule_next(dt_util.now())

        # A local, timezone-aware time: cronsim needs the zone to get daylight
        # saving right.
        schedule_next(dt_util.now())

        # Fires for any change to the core config, so the handler checks
        # whether the time zone is the part that moved.
        unsub_core_config = self._hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, core_config_changed
        )

        @callback
        def unattach() -> None:
            """Stop waiting."""
            unsub_core_config()
            stop_waiting()

        return unattach
