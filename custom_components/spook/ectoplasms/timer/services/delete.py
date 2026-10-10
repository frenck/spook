"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.timer import DOMAIN

from ....helper_collections import AbstractSpookDeleteHelperService


class SpookService(AbstractSpookDeleteHelperService):
    """Timer service to delete timers on the fly."""

    domain = DOMAIN
