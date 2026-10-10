"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_boolean import DOMAIN

from ....helper_collections import AbstractSpookDeleteHelperService


class SpookService(AbstractSpookDeleteHelperService):
    """Input boolean service to delete toggles on the fly."""

    domain = DOMAIN
