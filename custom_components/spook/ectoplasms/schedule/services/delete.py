"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.schedule import DOMAIN

from ....helper_collections import AbstractSpookDeleteHelperService


class SpookService(AbstractSpookDeleteHelperService):
    """Schedule service to delete schedules on the fly."""

    domain = DOMAIN
