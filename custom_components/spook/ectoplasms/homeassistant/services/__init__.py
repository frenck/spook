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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....const import DOMAIN
from ....errors import entity_not_found

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

CONF_ASSISTANTS = "assistants"
CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_DOMAIN = "domain"

CONFIG_ENTRY_SERVICE_SCHEMA = {
    vol.Optional(CONF_CONFIG_ENTRY_ID): vol.All(cv.ensure_list, [cv.string]),
    # Every entry of these integrations: the ones added later included, which
    # a list of entry IDs written down today would miss.
    vol.Optional(CONF_DOMAIN): vol.All(cv.ensure_list, [cv.string]),
}


def async_config_entry_ids(hass: HomeAssistant, call: ServiceCall) -> list[str]:
    """Return the integration entries an action asks for, by ID and by domain.

    A domain without any entries is refused rather than skipped: a typo in it
    would otherwise do nothing, and say nothing about it either.
    """
    entry_ids: list[str] = list(call.data.get(CONF_CONFIG_ENTRY_ID, []))
    domains: list[str] = call.data.get(CONF_DOMAIN, [])

    if not entry_ids and not domains:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="integration_entries_required",
        )

    for domain in domains:
        if not (entries := hass.config_entries.async_entries(domain)):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="integration_without_entries",
                translation_placeholders={
                    "domain": domain,
                },
            )
        entry_ids.extend(
            entry.entry_id for entry in entries if entry.entry_id not in entry_ids
        )

    return entry_ids


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
            raise entity_not_found(entity_id)

    for entity_id in entity_ids:
        for assistant in call.data[CONF_ASSISTANTS]:
            async_expose_entity(hass, assistant, entity_id, should_expose=should_expose)
