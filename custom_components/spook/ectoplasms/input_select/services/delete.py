"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_select import DOMAIN

from ....helper_collections import AbstractSpookDeleteHelperService


class SpookService(AbstractSpookDeleteHelperService):
    """Input select service to delete dropdowns on the fly."""

    domain = DOMAIN
