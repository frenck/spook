"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.schedule import (
    BASE_SCHEMA,
    DOMAIN,
    STORAGE_SCHEDULE_SCHEMA,
)

from ....helper_collections import AbstractSpookCreateHelperService


class SpookService(AbstractSpookCreateHelperService):
    """Schedule service to create a new weekly schedule on the fly.

    Core keeps no list of storage fields for a schedule. These are the fields
    its helper dialog is checked against: overlapping or backwards time
    blocks are refused, and the times come out the way storage keeps them.
    """

    domain = DOMAIN
    fields = BASE_SCHEMA | STORAGE_SCHEDULE_SCHEMA
