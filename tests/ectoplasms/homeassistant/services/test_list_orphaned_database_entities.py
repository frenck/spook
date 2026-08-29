"""Tests for the homeassistant.list_orphaned_database_entities action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.core import SupportsResponse
from homeassistant.helpers.recorder import DATA_INSTANCE
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.homeassistant.services.list_orphaned_database_entities import (
    SpookService,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_RECORDED = {"sensor.still_here", "sensor.long_gone", "sensor.also_gone"}


def _install_fake_recorder(hass: HomeAssistant) -> list[Any]:
    """Install a recorder whose executor hands back a fixed set of entity IDs.

    Returns the list the executor records what it was asked to run in, so a
    test can tell the query went to the recorder rather than to a database
    connection of Spook's own making.
    """
    ran: list[Any] = []

    async def _async_add_executor_job(func: Any, *_args: Any) -> Any:
        ran.append(func)
        return _RECORDED

    hass.data[DATA_INSTANCE] = SimpleNamespace(
        async_add_executor_job=_async_add_executor_job,
    )
    return ran


async def test_it_lists_what_the_database_kept_and_the_house_forgot(
    hass: HomeAssistant,
) -> None:
    """Recorded entity IDs with no state left are the orphans."""
    ran = _install_fake_recorder(hass)
    hass.states.async_set("sensor.still_here", "1")

    # Set up for real, because Spook does not register a service on somebody
    # else's domain until that integration is loaded.
    assert await async_setup_component(hass, "homeassistant", {})

    service = SpookService(hass)
    service.async_register()

    response = await hass.services.async_call(
        "homeassistant",
        "list_orphaned_database_entities",
        blocking=True,
        return_response=True,
    )

    orphaned = {"sensor.long_gone", "sensor.also_gone"}
    assert set(response["entities"]) == orphaned
    assert response["count"] == len(orphaned)
    assert ran, "the query did not go through the recorder"


async def test_the_action_answers_only_when_asked(hass: HomeAssistant) -> None:
    """It is a response-only action, so a call without one gets nothing back."""
    _install_fake_recorder(hass)

    assert SpookService.supports_response is SupportsResponse.ONLY
