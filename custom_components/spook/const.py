"""Spook - Your homie."""

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "spook"
LOGGER = logging.getLogger(__package__)

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]
