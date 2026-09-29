"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_text import DOMAIN, STORAGE_FIELDS

from ....helper_collections import AbstractSpookCreateHelperService


class SpookService(AbstractSpookCreateHelperService):
    """Input text service to create a new text helper on the fly."""

    domain = DOMAIN
    fields = STORAGE_FIELDS
