"""Spook - Not your homie."""

from homeassistant.const import Platform

DOMAIN = "spook_template"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]
