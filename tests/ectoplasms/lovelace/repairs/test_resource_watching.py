"""Tests that both resource repairs notice the resource list changing.

`EVENT_LOVELACE_UPDATED` is fired when a dashboard configuration is saved, not
when a resource is added or removed. Those go to the collection's own
listeners. A repair watching only the events would look once at startup and
then never again until something unrelated happened.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components.lovelace.resources import RESOURCE_STORAGE_KEY
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.lovelace.repairs import (
    duplicate_resources,
    missing_resources,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_MODULES = (duplicate_resources, missing_resources)


def _ids(module: object) -> str:
    """Name the parametrised case after its repair."""
    return module.SpookRepair.repair  # type: ignore[attr-defined]


@pytest.mark.parametrize("module", _MODULES, ids=_ids)
async def test_it_subscribes_to_the_resource_collection(
    hass: HomeAssistant,
    hass_storage: dict,
    module: object,
) -> None:
    """Activation has to reach the collection, not just the event bus."""
    hass_storage[RESOURCE_STORAGE_KEY] = {
        "version": 1,
        "key": RESOURCE_STORAGE_KEY,
        "data": {"items": [{"id": "1", "type": "module", "url": "/local/card.js"}]},
    }
    assert await async_setup_component(hass, "lovelace", {})
    await hass.async_block_till_done()

    resources = hass.data["lovelace"].resources
    await resources.async_get_info()
    before = len(resources.listeners)

    repair = module.SpookRepair(hass)  # type: ignore[attr-defined]
    await repair.async_activate()
    await hass.async_block_till_done()

    assert len(resources.listeners) == before + 1, (
        "the repair did not subscribe to resource changes"
    )

    # And it lets go again, rather than leaving a listener behind.
    await repair.async_deactivate()
    assert len(resources.listeners) == before


async def test_adding_a_duplicate_resource_raises_the_issue(
    hass: HomeAssistant,
    hass_storage: dict,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The whole point: a resource added from Settings is noticed.

    Nothing on the event bus says this happened, so a repair that only listens
    there would report it for the first time after a restart.
    """
    hass_storage[RESOURCE_STORAGE_KEY] = {
        "version": 1,
        "key": RESOURCE_STORAGE_KEY,
        "data": {"items": [{"id": "1", "type": "module", "url": "/local/card.js?v=1"}]},
    }
    assert await async_setup_component(hass, "lovelace", {})
    await hass.async_block_till_done()

    repair = duplicate_resources.SpookRepair(hass)
    await repair.async_activate()
    await hass.async_block_till_done()

    issue_id = "lovelace_duplicate_resources_module|/local/card.js"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None

    # The same card again, the way the Resources page would add it.
    resources = hass.data["lovelace"].resources
    await resources.async_create_item(
        {"res_type": "module", "url": "/local/card.js?v=2"}
    )
    # The inspection is debounced, so let its cooldown run out.
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    await repair.async_deactivate()
