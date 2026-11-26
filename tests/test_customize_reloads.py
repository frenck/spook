"""Tests for knowing when `customize:` was read again."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core_config import DATA_CUSTOMIZE
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.customize_reloads import async_follow_customize_reloads
from custom_components.spook.ectoplasms.homeassistant.repairs.unknown_customized_entities import (
    SpookRepair,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant


def _customizing(entity_id: str) -> dict[str, Any]:
    """Return a configuration customizing one entity."""
    return {"homeassistant": {"customize": {entity_id: {"icon": "mdi:ghost"}}}}


async def _let_time_pass(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    """Move the clock on, and let whatever comes due run."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _reload_core_config(hass: HomeAssistant, config: dict[str, Any]) -> None:
    """Reload the core configuration, reading ``config`` back."""
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=config,
    ):
        await hass.services.async_call(
            "homeassistant", "reload_core_config", blocking=True
        )


async def test_follows_a_core_config_reload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a real `reload_core_config` is followed once it is done.

    It sends nothing when it is done, it only swaps the customizations.
    """
    assert await async_setup_component(hass, "homeassistant", {})
    calls: list[None] = []
    stop = async_follow_customize_reloads(hass, lambda: calls.append(None))

    await _reload_core_config(hass, _customizing("light.ghost"))
    await _let_time_pass(hass, freezer, 1)
    stop()

    assert calls == [None]


async def test_waits_while_the_reload_is_still_reading(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a reload that takes its time is only followed once it is done."""
    calls: list[None] = []
    stop = async_follow_customize_reloads(hass, lambda: calls.append(None))

    hass.bus.async_fire(
        EVENT_CALL_SERVICE, {"domain": "homeassistant", "service": "reload_all"}
    )
    await _let_time_pass(hass, freezer, 5)
    assert not calls

    hass.data[DATA_CUSTOMIZE] = object()  # type: ignore[assignment]
    await _let_time_pass(hass, freezer, 1)
    stop()

    assert calls == [None]


async def test_gives_up_on_a_reload_that_failed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a reload that never brings new customizations is let go."""
    calls: list[None] = []
    stop = async_follow_customize_reloads(hass, lambda: calls.append(None))

    hass.bus.async_fire(
        EVENT_CALL_SERVICE,
        {"domain": "homeassistant", "service": "reload_core_config"},
    )
    # A second at a time: every check plans the next one from when it ran.
    for _ in range(61):
        await _let_time_pass(hass, freezer, 1)
    hass.data[DATA_CUSTOMIZE] = object()  # type: ignore[assignment]
    await _let_time_pass(hass, freezer, 1)
    stop()

    assert not calls


async def test_stopping_drops_a_wait_under_way(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test nothing is followed up once following stopped."""
    calls: list[None] = []
    stop = async_follow_customize_reloads(hass, lambda: calls.append(None))

    hass.bus.async_fire(
        EVENT_CALL_SERVICE,
        {"domain": "homeassistant", "service": "reload_core_config"},
    )
    stop()
    hass.data[DATA_CUSTOMIZE] = object()  # type: ignore[assignment]
    await _let_time_pass(hass, freezer, 1)

    assert not calls


async def test_other_reloads_are_not_followed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a service that does not read `customize:` starts no wait."""
    calls: list[None] = []
    stop = async_follow_customize_reloads(hass, lambda: calls.append(None))

    hass.bus.async_fire(
        EVENT_CALL_SERVICE,
        {"domain": "homeassistant", "service": "reload_custom_templates"},
    )
    hass.data[DATA_CUSTOMIZE] = object()  # type: ignore[assignment]
    await _let_time_pass(hass, freezer, 1)
    stop()

    assert not calls


async def test_a_customized_entity_that_is_gone_is_reported_after_a_reload(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test customizing a missing entity, then reloading, gets it reported.

    Before, nothing ever looked after a `reload_core_config`.
    """
    assert await async_setup_component(hass, "homeassistant", {})
    repair = SpookRepair(hass)
    await repair.async_activate()
    await _let_time_pass(hass, freezer, 5)

    await _reload_core_config(hass, _customizing("light.ghost"))
    await _let_time_pass(hass, freezer, 1)
    await _let_time_pass(hass, freezer, 5)

    issue_registry = ir.async_get(hass)
    assert any(
        domain == DOMAIN and issue_id.startswith("unknown_customized_entities_")
        for domain, issue_id in issue_registry.issues
    )

    await repair.async_deactivate()
