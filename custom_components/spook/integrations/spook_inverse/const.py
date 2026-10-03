"""Spook - Your homie."""

from homeassistant.const import Platform

DOMAIN = "spook_inverse"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SWITCH,
    Platform.VALVE,
]

# What each kind of inverse can be made of. An on/off helper or a light
# inverts as well as a switch does, and reads as well as a binary sensor.
SOURCE_DOMAINS: dict[str, list[str]] = {
    Platform.BINARY_SENSOR: [Platform.BINARY_SENSOR, "input_boolean", Platform.LIGHT],
    Platform.COVER: [Platform.COVER],
    Platform.SWITCH: [Platform.SWITCH, "input_boolean", Platform.LIGHT],
    Platform.VALVE: [Platform.VALVE],
}

CONF_HIDE_SOURCE = "hide_source"
CONF_INVERSE_POSITION = "inverse_position"
CONF_INVERSE_TILT = "inverse_tilt"
