"""Spook - Your homie. Creating and deleting UI helpers from actions."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import CONF_ENTITY_ID, CONF_ID
from homeassistant.core import SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES

from .services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
    from homeassistant.helpers.collection import DictStorageCollection
    from homeassistant.helpers.typing import VolDictType


@callback
def async_get_storage_collection(
    hass: HomeAssistant, domain: str
) -> DictStorageCollection:
    """Return the collection a helper domain keeps its UI-made helpers in.

    Home Assistant does not keep it anywhere public. The websocket command
    the frontend lists helpers with is bound to it, so that is where it is
    reached from. This is the one place that knows that, so the day core
    moves it, this breaks here, and says so, rather than in every action.
    """
    try:
        handler = hass.data["websocket_api"][f"{domain}/list"][0]
        storage_collection = handler.__self__.storage_collection
    except (KeyError, IndexError, AttributeError) as err:
        message = f"Could not reach the {domain} helpers Home Assistant keeps"
        raise HomeAssistantError(message) from err

    return storage_collection  # type: ignore[no-any-return]


class AbstractSpookCreateHelperService(AbstractSpookAdminService):
    """Create a UI helper, the way the helper dialog does.

    Hands back the entity ID of the new helper, since a script that makes its
    own helper needs to know what it ended up being called.
    """

    service = "create"
    supports_response = SupportsResponse.OPTIONAL
    fields: VolDictType

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Build each domain's schema from core's own fields.

        Core's fields, not a copy, so a field core adds shows up here without
        Spook having to catch up. On top comes `<domain>_id`, to pick the
        entity ID rather than have it follow the name.
        """
        super().__init_subclass__(**kwargs)
        cls.schema = {vol.Optional(f"{cls.domain}_id"): cv.slug, **cls.fields}

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        id_field = f"{self.domain}_id"
        data = {key: value for key, value in call.data.items() if key != id_field}
        collection = async_get_storage_collection(self.hass, self.domain)
        entity_registry = er.async_get(self.hass)

        # Two calls asking for the same entity ID at once would both find it
        # free, and the second would end up with a suffix it did not ask for.
        async with self.hass.data.setdefault(
            f"spook_{self.domain}_create_lock", asyncio.Lock()
        ):
            wanted_entity_id = (
                f"{self.domain}.{call.data[id_field]}"
                if id_field in call.data
                else None
            )
            # The state machine also holds entity IDs reserved for entities
            # still being added, which have no state yet.
            if wanted_entity_id and (
                entity_registry.async_get(wanted_entity_id)
                or not self.hass.states.async_available(wanted_entity_id)
            ):
                message = f"Entity ID {wanted_entity_id} is already taken"
                raise HomeAssistantError(message)

            item = await collection.async_create_item(data)
            entity_id = entity_registry.async_get_entity_id(
                self.domain, self.domain, item[CONF_ID]
            )

            # Home Assistant names the entity after the helper, as the UI does.
            # When an ID was asked for, it moves there instead.
            if wanted_entity_id and entity_id and entity_id != wanted_entity_id:
                try:
                    entity_registry.async_update_entity(
                        entity_id, new_entity_id=wanted_entity_id
                    )
                except ValueError as err:
                    # Taken after all, between the check and now. Leaving the
                    # helper behind under a name nobody asked for would be a
                    # failed call that still changed something.
                    await collection.async_delete_item(item[CONF_ID])
                    message = f"Entity ID {wanted_entity_id} is already taken"
                    raise HomeAssistantError(message) from err
                entity_id = wanted_entity_id

        if call.return_response:
            return {CONF_ENTITY_ID: entity_id}
        return None


class AbstractSpookDeleteHelperService(AbstractSpookAdminService):
    """Delete UI helpers, the way the helper dialog does.

    Helpers set up in YAML are refused: Home Assistant cannot delete those,
    only the YAML can. Everything in the list is checked before anything is
    deleted, since a deleted helper does not come back.
    """

    service = "delete"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Give each domain a schema that only takes its own entities."""
        super().__init_subclass__(**kwargs)
        cls.schema = {vol.Required(CONF_ENTITY_ID): cv.entities_domain(cls.domain)}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        component = self.hass.data[DATA_INSTANCES][self.domain]
        collection = async_get_storage_collection(self.hass, self.domain)
        entity_registry = er.async_get(self.hass)

        item_ids = []
        for entity_id in call.data[CONF_ENTITY_ID]:
            # Looked up in the registry rather than among the running
            # entities: a disabled helper is not running, but it is still
            # there, and still something that can be deleted.
            entry = entity_registry.async_get(entity_id)
            if (
                entry is not None
                and entry.platform == self.domain
                and entry.unique_id in collection.data
            ):
                item_ids.append(entry.unique_id)
                continue

            if entry is None and component.get_entity(entity_id) is None:
                message = f"Could not find {entity_id}"
                raise HomeAssistantError(message)

            # It exists, but not in the collection the UI keeps: YAML.
            message = f"{entity_id} is set up in YAML and cannot be deleted"
            raise HomeAssistantError(message)

        # The same helper twice in the list is still one helper. Deleting it a
        # second time would fail after the first had already gone through.
        for item_id in dict.fromkeys(item_ids):
            await collection.async_delete_item(item_id)
