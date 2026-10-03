"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

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

from .const import CONF_STATES, DOMAIN

if TYPE_CHECKING:
    from collections.abc import Mapping

_STATES_SELECTOR = selector.TextSelector(selector.TextSelectorConfig(multiple=True))


async def options_schema(handler: SchemaCommonFlowHandler) -> vol.Schema:
    """Generate options schema."""
    return vol.Schema(
        {
            vol.Required(CONF_ENTITY_ID): entity_selector_without_own_entities(
                cast(SchemaOptionsFlowHandler, handler.parent_handler),
                selector.EntitySelectorConfig(),
            ),
            vol.Optional(CONF_STATES): _STATES_SELECTOR,
        },
    )


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_ENTITY_ID): selector.EntitySelector(),
        vol.Optional(CONF_STATES): _STATES_SELECTOR,
    },
)

CONFIG_FLOW = {"user": SchemaFlowFormStep(CONFIG_SCHEMA)}
OPTIONS_FLOW = {"init": SchemaFlowFormStep(options_schema)}


class SpookTimeInStateConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle config flow for the Spook time in state helper."""

    VERSION = 1
    MINOR_VERSION = 1

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options.get(CONF_NAME, ""))
