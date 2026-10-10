"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.input_button import DOMAIN

from ....helper_collections import AbstractSpookDeleteHelperService


class SpookService(AbstractSpookDeleteHelperService):
    """Input button service to delete buttons on the fly."""

    domain = DOMAIN
