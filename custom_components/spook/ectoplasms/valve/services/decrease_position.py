"""Spook - Your homie."""

from __future__ import annotations

from ..stepping import AbstractStepPositionService


class SpookService(AbstractStepPositionService):
    """Valve service that moves it a step further closed."""

    service = "decrease_position"
    direction = -1
