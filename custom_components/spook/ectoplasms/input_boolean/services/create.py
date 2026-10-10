"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_boolean import DOMAIN, STORAGE_FIELDS

from ....helper_collections import AbstractSpookCreateHelperService


class SpookService(AbstractSpookCreateHelperService):
    """Input boolean service to create a new toggle on the fly."""

    domain = DOMAIN
    fields = STORAGE_FIELDS
