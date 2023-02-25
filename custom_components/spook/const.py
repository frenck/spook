"""Spook - Not your homie."""
import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "spook"
LOGGER = logging.getLogger(__package__)
PLATFORMS: Final = [Platform.SENSOR, Platform.SWITCH]
