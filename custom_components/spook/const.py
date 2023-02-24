"""Spook - Not your homey."""
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "spook"
PLATFORMS: Final = [Platform.SENSOR, Platform.SWITCH]
