"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_datetime import DOMAIN

from ....helper_collections import AbstractSpookDeleteHelperService


class SpookService(AbstractSpookDeleteHelperService):
    """Input datetime service to delete date and time helpers on the fly."""

    domain = DOMAIN
