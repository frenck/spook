"""Tests for the input_number.delete service."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

from collections.abc import Awaitable, Callable
import re
from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.input_number import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.input_number.services import delete

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er


StorageSetup = Callable[..., Awaitable[bool]]


@pytest.fixture
def storage_setup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> StorageSetup:
    """Set up the input number integration backed by storage."""

    async def _storage(
        items: list[dict[str, Any]] | None = None,
        config: dict[str, Any] | None = None,
    ) -> bool:
        hass_storage[DOMAIN] = {
            "key": DOMAIN,
            "version": 1,
            "data": {"items": items or []},
        }
        return await async_setup_component(hass, DOMAIN, config or {DOMAIN: {}})

    return _storage


@pytest.fixture
async def input_number_delete_service(
    hass: HomeAssistant,
    storage_setup: StorageSetup,
) -> None:
    """Set up input_number and register the Spook delete service."""
    assert await storage_setup(
        items=[
            {
                "id": "from_storage",
                "name": "From Storage",
                "min": 0,
                "max": 100,
                "step": 1,
                "mode": "slider",
            }
        ]
    )
    delete.SpookService(hass).async_register()


@pytest.mark.usefixtures("input_number_delete_service")
async def test_delete_service_deletes_editable_input_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the delete service deletes an editable input number helper."""
    entity_id = f"{DOMAIN}.from_storage"

    assert hass.states.get(entity_id) is not None
    assert (
        entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "from_storage") == entity_id
    )

    await hass.services.async_call(
        DOMAIN,
        "delete",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "from_storage") is None


async def test_delete_service_rejects_yaml_input_number(
    hass: HomeAssistant,
    storage_setup: StorageSetup,
) -> None:
    """Test the delete service rejects a YAML-backed input number helper."""
    assert await storage_setup(
        config={
            DOMAIN: {
                "from_yaml": {
                    CONF_NAME: "From YAML",
                    "initial": 5,
                    "min": 0,
                    "max": 10,
                }
            }
        }
    )
    delete.SpookService(hass).async_register()

    entity_id = f"{DOMAIN}.from_yaml"
    assert hass.states.get(entity_id) is not None

    with pytest.raises(HomeAssistantError, match=re.escape("input_number.from_yaml")):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert hass.states.get(entity_id) is not None
