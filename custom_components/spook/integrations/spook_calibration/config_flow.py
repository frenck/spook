"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
    entity_selector_without_own_entities,
)

from .const import CONF_FACTOR, CONF_OFFSET, DOMAIN

if TYPE_CHECKING:
    from collections.abc import Mapping

# Any number, typed in: a slider has no business choosing a correction.
_NUMBER_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step="any")
)

_CORRECTION_SCHEMA = {
    vol.Required(CONF_OFFSET, default=0): _NUMBER_SELECTOR,
    vol.Required(CONF_FACTOR, default=1): _NUMBER_SELECTOR,
}


async def options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Generate options schema."""
    return vol.Schema(
        {
            vol.Required(CONF_ENTITY_ID): entity_selector_without_own_entities(
                cast(SchemaOptionsFlowHandler, handler.parent_handler),
                selector.EntitySelectorConfig(domain=SENSOR_DOMAIN),
            ),
            **_CORRECTION_SCHEMA,
        },
    )


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
        ),
        **_CORRECTION_SCHEMA,
    },
)

CONFIG_FLOW = {"user": SchemaFlowFormStep(CONFIG_SCHEMA)}
OPTIONS_FLOW = {"init": SchemaFlowFormStep(options_schema)}


class SpookCalibrationConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle config flow for the Spook calibration helper."""

    VERSION = 1
    MINOR_VERSION = 1

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options.get(CONF_NAME, ""))
