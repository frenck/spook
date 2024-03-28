"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_select import DOMAIN

from ...select.services.random import SpookService as SelectRandomSpookService


class SpookService(SelectRandomSpookService):
    """Input select entity service, select a random option.

    Clone of the select_random service, but for input_select entities.
    """

    domain = DOMAIN
