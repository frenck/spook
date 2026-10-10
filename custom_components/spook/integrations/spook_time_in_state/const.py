"""Spook - Your homie."""

DOMAIN = "spook_time_in_state"

# The states that count. Left empty, any change does: the sensor then tells
# since when the source has been in the state it is in now. Filled in, only
# becoming one of these does: since when it last became, say, `on`.
CONF_STATES = "states"

ATTR_SOURCE_STATE = "source_state"
ATTR_OBSERVED = "observed"
