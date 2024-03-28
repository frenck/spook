"""Spook - Your homie."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
    SchemaOptionsFlowHandler,
    entity_selector_without_own_entities,
)

from .const import CONF_HIDE_SOURCE, DOMAIN, PLATFORMS

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping


async def options_schema(
    domain: str | list[str],
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Generate options schema."""
    return vol.Schema(
        {
            vol.Required(CONF_ENTITY_ID): entity_selector_without_own_entities(
                cast(SchemaOptionsFlowHandler, handler.parent_handler),
                selector.EntitySelectorConfig(domain=domain),
            ),
            vol.Required(CONF_HIDE_SOURCE, default=False): selector.BooleanSelector(),
        },
    )


def config_schema(domain: str | list[str]) -> vol.Schema:
    """Generate config schema."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=domain),
            ),
            vol.Required(CONF_HIDE_SOURCE, default=False): selector.BooleanSelector(),
        },
    )


async def choose_options_step(options: dict[str, Any]) -> str:
    """Return next step_id for options flow according to inverse_type."""
    return cast(str, options["inverse_type"])


def set_inverse_type(
    inverse_type: str,
) -> Callable[
    [SchemaCommonFlowHandler, dict[str, Any]],
    Coroutine[Any, Any, dict[str, Any]],
]:
    """Set inverse type."""

    async def _set_inverse_type(
        _: SchemaCommonFlowHandler,
        user_input: dict[str, Any],
    ) -> dict[str, Any]:
        """Add inverse type to user input."""
        return {"inverse_type": inverse_type, **user_input}

    return _set_inverse_type


CONFIG_FLOW = {
    "user": SchemaFlowMenuStep(PLATFORMS),
    Platform.BINARY_SENSOR: SchemaFlowFormStep(
        config_schema(Platform.BINARY_SENSOR),
        validate_user_input=set_inverse_type(Platform.BINARY_SENSOR),
    ),
    Platform.SWITCH: SchemaFlowFormStep(
        config_schema(Platform.SWITCH),
        validate_user_input=set_inverse_type(Platform.SWITCH),
    ),
}


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(next_step=choose_options_step),
    Platform.BINARY_SENSOR: SchemaFlowFormStep(
        partial(options_schema, Platform.BINARY_SENSOR),
    ),
    Platform.SWITCH: SchemaFlowFormStep(partial(options_schema, Platform.SWITCH)),
}


class SpookInverseConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle config flow for Spook inverse helper."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    @callback
    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, options["name"]) if "name" in options else ""

    @callback
    def async_config_flow_finished(self, options: Mapping[str, Any]) -> None:
        """Hide the source entity if requested."""
        if options[CONF_HIDE_SOURCE]:
            _async_hide_source(
                self.hass,
                options[CONF_ENTITY_ID],
                er.RegistryEntryHider.INTEGRATION,
            )

    @callback
    @staticmethod
    def async_options_flow_finished(
        hass: HomeAssistant,
        options: Mapping[str, Any],
    ) -> None:
        """Hide or unhide the source entity as requested."""
        hidden_by = (
            er.RegistryEntryHider.INTEGRATION if options[CONF_HIDE_SOURCE] else None
        )
        _async_hide_source(hass, options[CONF_ENTITY_ID], hidden_by)


def _async_hide_source(
    hass: HomeAssistant,
    source_entity_id: str,
    hidden_by: er.RegistryEntryHider | None,
) -> None:
    """Hide or unhide inverse source."""
    registry = er.async_get(hass)
    if not (entity_id := er.async_resolve_entity_id(registry, source_entity_id)):
        return
    if entity_id not in registry.entities:
        return
    registry.async_update_entity(entity_id, hidden_by=hidden_by)
