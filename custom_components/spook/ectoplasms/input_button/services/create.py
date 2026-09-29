"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_button import DOMAIN, STORAGE_FIELDS

from ....helper_collections import AbstractSpookCreateHelperService


class SpookService(AbstractSpookCreateHelperService):
    """Input button service to create a new button on the fly."""

    domain = DOMAIN
    fields = STORAGE_FIELDS
