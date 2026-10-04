"""Spook - Your homie."""

from __future__ import annotations

from ..stepping import AbstractStepVolumeService


class SpookService(AbstractStepVolumeService):
    """Media player service that turns the volume up a step."""

    service = "increase_volume"
    direction = 1
