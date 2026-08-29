"""Spook - Your homie."""

from __future__ import annotations

from ..stepping import AbstractStepBrightnessService


class SpookService(AbstractStepBrightnessService):
    """Light service that turns down what is already lit.

    It stops at the dimmest a light goes rather than switching it off, so
    holding a dim-down button leaves the room lit rather than dark.
    """

    service = "decrease_brightness"
    direction = -1
