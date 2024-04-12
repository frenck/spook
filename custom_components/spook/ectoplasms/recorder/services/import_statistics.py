"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.recorder import DOMAIN
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
)
from homeassistant.core import ServiceCall, valid_entity_id
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.components.recorder.models import StatisticMetaData


class SpookService(AbstractSpookAdminService):
    """Recorder integration service to import statistics."""

    domain = DOMAIN
    service = "import_statistics"
    schema = {
        vol.Required("has_mean"): bool,
        vol.Required("has_sum"): bool,
        vol.Optional("name", default=None): vol.Any(None, str),
        vol.Required("source"): str,
        vol.Required("statistic_id"): str,
        vol.Optional("unit_of_measurement", default=None): vol.Any(None, str),
        vol.Required("stats"): [
            {
                vol.Required("start"): cv.datetime,
                vol.Optional("mean"): vol.Any(float, int),
                vol.Optional("min"): vol.Any(float, int),
                vol.Optional("max"): vol.Any(float, int),
                vol.Optional("last_reset", default=None): vol.Any(None, cv.datetime),
                vol.Optional("state"): vol.Any(float, int),
                vol.Optional("sum"): vol.Any(float, int),
            },
        ],
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        metadata: StatisticMetaData = {
            "has_mean": call.data["has_mean"],
            "has_sum": call.data["has_sum"],
            "name": call.data["name"],
            "source": call.data["source"],
            "statistic_id": call.data["statistic_id"],
            "unit_of_measurement": call.data["unit_of_measurement"],
        }

        if valid_entity_id(call.data["statistic_id"]):
            async_import_statistics(self.hass, metadata, call.data["stats"])
        else:
            async_add_external_statistics(self.hass, metadata, call.data["stats"])
