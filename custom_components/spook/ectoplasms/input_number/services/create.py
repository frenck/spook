"""Spook - Your homie."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.input_number import (
    CONF_MAX,
    CONF_MIN,
    DOMAIN,
    STORAGE_FIELDS,
)

from ....helper_collections import AbstractSpookCreateHelperService

# Core requires a minimum and a maximum. This action never has: it started
# out with 0 and 100, and calls written against that keep working.
_FIELDS = {
    **{
        marker: validator
        for marker, validator in STORAGE_FIELDS.items()
        if marker not in (CONF_MIN, CONF_MAX)
    },
    vol.Optional(CONF_MIN, default=0): vol.Coerce(float),
    vol.Optional(CONF_MAX, default=100): vol.Coerce(float),
}


class SpookService(AbstractSpookCreateHelperService):
    """Input number service to create a new helper on the fly."""

    domain = DOMAIN
    fields = _FIELDS
