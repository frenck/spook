"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

# Home Assistant keeps the exposure settings, and the list of assistants that
# have them, in this module. There is no public helper for either.
from homeassistant.components.homeassistant.exposed_entities import (
    KNOWN_ASSISTANTS,
    async_expose_entity,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

CONF_ASSISTANTS = "assistants"

EXPOSURE_SERVICE_SCHEMA = {
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(CONF_ASSISTANTS): vol.All(cv.ensure_list, [vol.In(KNOWN_ASSISTANTS)]),
}


def async_set_voice_assistant_exposure(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    should_expose: bool,
) -> None:
    """Set whether entities are exposed to the given voice assistants.

    Shared by the expose and unexpose actions, which differ only in what they
    set it to.
    """
    entity_registry = er.async_get(hass)

    # Checked up front, so an unknown entity halfway down the list does not
    # leave the ones before it already changed, with nothing saying which.
    entity_ids = call.data[ATTR_ENTITY_ID]
    for entity_id in entity_ids:
        if (
            hass.states.get(entity_id) is None
            and entity_registry.async_get(entity_id) is None
        ):
            msg = f"Unknown entity: {entity_id}"
            raise HomeAssistantError(msg)

    for entity_id in entity_ids:
        for assistant in call.data[CONF_ASSISTANTS]:
            async_expose_entity(hass, assistant, entity_id, should_expose=should_expose)
