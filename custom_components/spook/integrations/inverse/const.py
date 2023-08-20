"""Spook - Not your homie."""

from homeassistant.const import Platform

DOMAIN = "spook_inverse"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

CONF_HIDE_SOURCE = "hide_source"
