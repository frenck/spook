"""Spook - Your homie."""

from __future__ import annotations

from ..stepping import AbstractStepTemperatureService


class SpookService(AbstractStepTemperatureService):
    """Climate service that turns the setpoint down a step."""

    service = "decrease_temperature"
    direction = -1
