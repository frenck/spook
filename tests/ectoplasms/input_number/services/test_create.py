"""Tests for the input_number.create service."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

from collections.abc import Awaitable, Callable
import re
from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.input_number import (
    CONF_INITIAL,
    CONF_MAX,
    CONF_MIN,
    CONF_STEP,
    DOMAIN,
)
from homeassistant.const import ATTR_EDITABLE, ATTR_FRIENDLY_NAME, CONF_MODE, CONF_NAME
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.input_number.services import create

if TYPE_CHECKING:
    from homeassistant.helpers import entity_registry as er

    from tests.common import MockUser


INPUT_VALUE = 10
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
async def input_number_create_service(
    hass: HomeAssistant,
    storage_setup: StorageSetup,
) -> None:
    """Set up input_number and register the Spook create service."""
    assert await storage_setup(None)
    create.SpookService(hass).async_register()


@pytest.mark.usefixtures("input_number_create_service")
async def test_create_service_creates_input_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_admin_user: MockUser,
) -> None:
    """Test the create service creates an input number helper."""
    entity_id = f"{DOMAIN}.new_input"

    assert hass.states.get(entity_id) is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "new_input") is None

    await hass.services.async_call(
        DOMAIN,
        "create",
        {
            CONF_NAME: "New Input",
            create.CONF_INPUT_NUMBER_ID: "new_input",
            CONF_MIN: 0,
            CONF_MAX: 20,
            CONF_INITIAL: INPUT_VALUE,
            CONF_STEP: 1,
            CONF_MODE: "slider",
        },
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == INPUT_VALUE
    assert state.attributes[ATTR_FRIENDLY_NAME] == "New Input"
    assert state.attributes[ATTR_EDITABLE]
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "new_input") == entity_id


@pytest.mark.usefixtures("input_number_create_service")
async def test_create_service_rejects_duplicate_input_number_id(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """Test the create service rejects a duplicate input number ID."""
    await hass.services.async_call(
        DOMAIN,
        "create",
        {
            CONF_NAME: "Existing Input",
            create.CONF_INPUT_NUMBER_ID: "existing_id",
        },
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("input_number.existing_id"),
    ):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {
                CONF_NAME: "Duplicate Input",
                create.CONF_INPUT_NUMBER_ID: "existing_id",
            },
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )

    assert hass.states.get(f"{DOMAIN}.duplicate_input") is None


async def test_create_service_rejects_yaml_input_number_id(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    storage_setup: StorageSetup,
) -> None:
    """Test the create service rejects a YAML-backed input number ID."""
    assert await storage_setup(
        config={DOMAIN: {"from_yaml": {"initial": 5, "min": 0, "max": 10}}},
    )
    create.SpookService(hass).async_register()

    with pytest.raises(
        HomeAssistantError,
        match=re.escape("input_number.from_yaml"),
    ):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {
                CONF_NAME: "Duplicate Input",
                create.CONF_INPUT_NUMBER_ID: "from_yaml",
            },
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )

    assert hass.states.get(f"{DOMAIN}.duplicate_input") is None


@pytest.mark.usefixtures("input_number_create_service")
async def test_create_service_without_input_number_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_admin_user: MockUser,
) -> None:
    """Test the create service creates an input number helper from its name."""
    entity_id = f"{DOMAIN}.generated_input"

    assert hass.states.get(entity_id) is None

    await hass.services.async_call(
        DOMAIN,
        "create",
        {CONF_NAME: "Generated Input"},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is not None
    assert (
        entity_registry.async_get_entity_id(
            DOMAIN,
            DOMAIN,
            "generated_input",
        )
        == entity_id
    )
