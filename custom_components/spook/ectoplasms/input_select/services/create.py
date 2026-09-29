"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_select import DOMAIN, STORAGE_FIELDS

from ....helper_collections import AbstractSpookCreateHelperService


class SpookService(AbstractSpookCreateHelperService):
    """Input select service to create a new dropdown on the fly."""

    domain = DOMAIN
    fields = STORAGE_FIELDS
