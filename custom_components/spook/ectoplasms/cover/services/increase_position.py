"""Spook - Your homie."""

from __future__ import annotations

from ..stepping import AbstractStepPositionService


class SpookService(AbstractStepPositionService):
    """Cover service that moves it a step further open."""

    service = "increase_position"
    direction = 1
