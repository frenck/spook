"""Tests for the icons of the actions Spook adds to other integrations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.helpers.icon import ICON_CACHE, async_get_icons
from homeassistant.util.yaml import load_yaml_dict

from custom_components.spook import service_icons
from custom_components.spook.service_icons import (
    async_inject_service_icons,
    async_remove_service_icons,
)

if TYPE_CHECKING:
    import pytest

    from homeassistant.core import HomeAssistant

SPOOK = Path(service_icons.__file__).parent

# One of Spook's actions on the light domain, and one of the light domain's
# own actions, which has an icon in Home Assistant already.
SPOOKS_ACTION = ("light", "increase_brightness", "light_increase_brightness")
CORES_ACTION = ("light", "turn_on", "light_increase_brightness")


async def _light_icons(hass: HomeAssistant) -> dict:
    """Return the action icons Home Assistant hands out for the light domain."""
    return (await async_get_icons(hass, "services", {"light"}))["light"]


def test_every_action_has_an_icon() -> None:
    """Test every action in services.yaml has an icon, and nothing else does."""
    services = load_yaml_dict(str(SPOOK / "services.yaml"))
    icons = json.loads((SPOOK / "icons.json").read_text())["services"]

    assert set(icons) == set(services)


async def test_action_on_another_domain_gets_spooks_icon(hass: HomeAssistant) -> None:
    """Test Home Assistant hands out Spook's icon for Spook's action."""
    injected: set[tuple[str, str]] = set()

    await async_inject_service_icons(hass, [SPOOKS_ACTION], injected)

    assert (await _light_icons(hass))["increase_brightness"] == {
        "service": "mdi:brightness-7"
    }
    assert injected == {("light", "increase_brightness")}


async def test_action_with_an_icon_of_its_own_keeps_it(hass: HomeAssistant) -> None:
    """Test an action Home Assistant already has an icon for keeps that one."""
    original = (await _light_icons(hass))["turn_on"]
    injected: set[tuple[str, str]] = set()

    await async_inject_service_icons(hass, [CORES_ACTION], injected)

    assert (await _light_icons(hass))["turn_on"] == original
    assert not injected


async def test_removing_takes_out_only_spooks_icons(hass: HomeAssistant) -> None:
    """Test unloading takes out what Spook put in, and nothing of core's."""
    original = (await _light_icons(hass))["turn_on"]
    injected: set[tuple[str, str]] = set()
    await async_inject_service_icons(hass, [SPOOKS_ACTION, CORES_ACTION], injected)

    async_remove_service_icons(hass, injected)

    icons = await _light_icons(hass)
    assert "increase_brightness" not in icons
    assert icons["turn_on"] == original
    assert not injected


async def test_injecting_again_is_harmless(hass: HomeAssistant) -> None:
    """Test injecting again, as a domain loading later does, changes nothing."""
    injected: set[tuple[str, str]] = set()

    await async_inject_service_icons(hass, [SPOOKS_ACTION], injected)
    await async_inject_service_icons(hass, [SPOOKS_ACTION], injected)

    assert (await _light_icons(hass))["increase_brightness"] == {
        "service": "mdi:brightness-7"
    }
    assert injected == {("light", "increase_brightness")}


async def test_unexpected_cache_skips_the_icons(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a cache in a shape Spook does not know costs the icons, not Spook."""
    hass.data[ICON_CACHE] = object()
    injected: set[tuple[str, str]] = set()

    await async_inject_service_icons(hass, [SPOOKS_ACTION], injected)
    async_remove_service_icons(hass, {("light", "increase_brightness")})

    assert not injected
    assert "Unable to access Home Assistant's icon cache" in caplog.text


async def test_unexpected_services_or_domain_skips_the_icons(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a cache that is a dict outside but not inside costs the icons only.

    Both the actions and a single domain can change shape on their own, and
    neither may take Spook down with it.
    """
    await async_get_icons(hass, "services", {"light", "spook"})
    # pylint: disable-next=protected-access
    categories = hass.data[ICON_CACHE]._cache  # noqa: SLF001
    injected: set[tuple[str, str]] = set()

    categories["services"]["light"] = "not a mapping"
    await async_inject_service_icons(hass, [SPOOKS_ACTION], injected)
    async_remove_service_icons(hass, {("light", "increase_brightness")})

    assert not injected

    # Home Assistant itself trips over this one when loading, so it is the
    # way out that has to cope with it on its own.
    categories["services"] = "not a mapping"
    await async_inject_service_icons(hass, [SPOOKS_ACTION], injected)
    async_remove_service_icons(hass, {("light", "increase_brightness")})

    assert not injected
    assert "Home Assistant's icon cache has an unexpected structure" in caplog.text
