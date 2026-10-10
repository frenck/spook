"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_number import DOMAIN

from ....helper_collections import AbstractSpookDeleteHelperService


class SpookService(AbstractSpookDeleteHelperService):
    """Input number service to delete input numbers on the fly."""

    domain = DOMAIN
