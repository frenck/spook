"""Spook - Your homie."""

import logging
import os
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "spook"
LOGGER = logging.getLogger(__package__)

# Only for the screenshots of the website (documentation/screenshots), whose
# Home Assistant sets it. A few things in Spook wait a long while on purpose
# before they speak up, and that home has minutes, not hours. With this on,
# they do not wait. Off unless the environment says otherwise.
SCREENSHOT_HOME: Final = os.environ.get("SPOOK_SCREENSHOT_HOME") == "1"

# How long, in seconds, CPU-bound work reading configurations may hold the
# event loop before it hands the loop back. Reading is done in steps small
# enough for this, so how long a house takes to read does not decide how long
# Home Assistant is held up. #2005.
YIELD_AFTER: Final = 0.005

# Asked for once, at the end of setting Spook up, and nowhere else.
NEWSLETTER_URL: Final = "https://frenck.dev/newsletter/"
REPOSITORY_URL: Final = "https://github.com/frenck/spook"
SPONSOR_URL: Final = "https://github.com/sponsors/frenck"

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.UPDATE,
]
