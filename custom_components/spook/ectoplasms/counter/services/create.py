"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.counter import DOMAIN, STORAGE_FIELDS

from ....helper_collections import AbstractSpookCreateHelperService


class SpookService(AbstractSpookCreateHelperService):
    """Counter service to create a new counter on the fly."""

    domain = DOMAIN
    fields = STORAGE_FIELDS
