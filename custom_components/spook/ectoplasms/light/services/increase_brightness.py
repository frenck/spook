"""Spook - Your homie."""

from __future__ import annotations

from ..stepping import AbstractStepBrightnessService


class SpookService(AbstractStepBrightnessService):
    """Light service that turns up what is already lit.

    Lights that are off stay off: Home Assistant reads an off light as
    brightness zero and turns it on from there, so asking a room for more
    light would switch on everything somebody had deliberately turned off.
    """

    service = "increase_brightness"
    direction = 1
