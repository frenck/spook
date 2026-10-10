"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.timer import DOMAIN, STORAGE_FIELDS

from ....helper_collections import AbstractSpookCreateHelperService


class SpookService(AbstractSpookCreateHelperService):
    """Timer service to create a new timer on the fly."""

    domain = DOMAIN
    fields = STORAGE_FIELDS
