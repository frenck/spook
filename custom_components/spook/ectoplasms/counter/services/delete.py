"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.counter import DOMAIN

from ....helper_collections import AbstractSpookDeleteHelperService


class SpookService(AbstractSpookDeleteHelperService):
    """Counter service to delete counters on the fly."""

    domain = DOMAIN
