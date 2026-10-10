"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_text import DOMAIN

from ....helper_collections import AbstractSpookDeleteHelperService


class SpookService(AbstractSpookDeleteHelperService):
    """Input text service to delete text helpers on the fly."""

    domain = DOMAIN
