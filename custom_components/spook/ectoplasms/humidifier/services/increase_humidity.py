"""Spook - Your homie."""

from __future__ import annotations

from ..stepping import AbstractStepHumidityService


class SpookService(AbstractStepHumidityService):
    """Humidifier service that turns the target humidity up a step."""

    service = "increase_humidity"
    direction = 1
