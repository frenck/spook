"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_datetime import (
    DOMAIN,
    STORAGE_FIELDS,
    valid_initial,
)

from ....helper_collections import AbstractSpookCreateHelperService


class SpookService(AbstractSpookCreateHelperService):
    """Input datetime service to create a new date and/or time on the fly.

    The collection checks there is a date or a time, but not that the initial
    value can be read. That only fails once the helper is already stored.
    """

    domain = DOMAIN
    fields = STORAGE_FIELDS
    validators = (valid_initial,)
