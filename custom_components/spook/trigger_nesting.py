"""Spook - Your homie. Attaching triggers on behalf of another trigger."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers import trigger as trigger_helper

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import CALLBACK_TYPE, HomeAssistant
    from homeassistant.helpers.typing import ConfigType


@callback
def _log(level: int, message: str, **kwargs: Any) -> None:
    """Take the log line Home Assistant writes about a nested trigger.

    `async_initialize_triggers` insists on somewhere to write, and what it
    writes is about a trigger the user did not attach themselves, so it goes
    to Spook's logger rather than an automation's.
    """
    LOGGER.log(level, "Spook nested trigger: %s", message, **kwargs)


async def async_attach_nested(
    hass: HomeAssistant,
    configs: list[ConfigType],
    action: Callable,
    name: str,
    consequence: str,
) -> CALLBACK_TYPE | None:
    """Attach triggers on behalf of a Spook trigger, and say if it worked.

    Returns `None` when nothing could be attached, having said so in the log.
    Home Assistant already logs why; what it cannot know is what that costs
    the trigger asking, and going quiet about that is how a trigger ends up
    looking healthy while it can no longer do its job.

    `name` and `consequence` are read straight into that line: "Spook could
    not attach {name}, {consequence}". Which is why the consequence comes from
    the caller. A sequence missing a step never fires again, while one missing
    its optional reset triggers fires perfectly well and has only stopped
    being interruptible.

    `action` has to be a function, not an object with an async `__call__`.
    Home Assistant decides whether to await an action by inspecting it, and an
    instance is not recognised as awaitable: the coroutine gets created,
    dropped, and the trigger never hears anything. Measured, at the cost of an
    afternoon.
    """
    unsub = await trigger_helper.async_initialize_triggers(
        hass, configs, action, DOMAIN, name, _log
    )

    if unsub is None:
        LOGGER.warning("Spook could not attach %s, %s", name, consequence)

    return unsub
