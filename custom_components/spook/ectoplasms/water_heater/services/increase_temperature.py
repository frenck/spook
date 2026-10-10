"""Spook - Your homie."""

from __future__ import annotations

from ..stepping import AbstractStepTemperatureService


class SpookService(AbstractStepTemperatureService):
    """Water heater service that turns the setpoint up a step."""

    service = "increase_temperature"
    direction = 1
