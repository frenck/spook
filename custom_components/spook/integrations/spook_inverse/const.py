"""Spook - Your homie."""

from homeassistant.const import Platform

DOMAIN = "spook_inverse"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

CONF_HIDE_SOURCE = "hide_source"
CONF_INVERSE_POSTITION = "inverse_position"
CONF_INVERSE_TILT = "inverse_tilt"
