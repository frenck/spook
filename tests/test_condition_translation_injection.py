"""Tests for putting Spook's condition strings where the UI looks for them."""

# ruff: noqa: SLF001
# pylint: disable=protected-access
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.translation import async_get_cached_translations
import pytest  # noqa: TC002

from custom_components.spook import translation_injection
from custom_components.spook.condition import SpookConditionManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_NAME = "component.automation.conditions.triggered_by_user.name"
_FIELD = "component.automation.conditions.triggered_by_user.fields.user_id.name"
_NOT_NAME = "component.automation.conditions.not_triggered_by_user.name"


def _automation_conditions(hass: HomeAssistant) -> dict[str, str]:
    """Return the cached condition translations for the automation domain."""
    return async_get_cached_translations(hass, "en", "conditions", "automation")


async def test_strings_land_under_the_automation_domain(hass: HomeAssistant) -> None:
    """Spook's condition strings are filed where the UI will ask for them.

    Home Assistant loads translations per integration, so a condition keyed
    `automation.triggered_by_user` gets looked up under the automation
    integration, which knows nothing about it.
    """
    assert _NAME not in _automation_conditions(hass)

    manager = SpookConditionManager(hass)
    await manager.async_inject_condition_translations()

    translations = _automation_conditions(hass)
    assert translations[_NAME] == "Triggered by a user 👻"
    assert translations[_FIELD] == "Users"
    assert translations[_NOT_NAME] == "Not triggered by a user 👻"


async def test_injection_is_undone_on_unload(hass: HomeAssistant) -> None:
    """Unloading Spook leaves the automation domain as it was found."""
    manager = SpookConditionManager(hass)
    await manager.async_inject_condition_translations()
    assert _NAME in _automation_conditions(hass)

    manager.async_on_unload()

    assert _NAME not in _automation_conditions(hass)


async def test_injecting_twice_still_restores_cleanly(hass: HomeAssistant) -> None:
    """A language change re-injects, and must not remember its own writes.

    Recording Spook's own string as the value to restore would leave it
    behind forever, which is the bug this guards.
    """
    manager = SpookConditionManager(hass)
    await manager.async_inject_condition_translations()
    await manager.async_inject_condition_translations()

    manager.async_on_unload()

    assert _NAME not in _automation_conditions(hass)


async def test_missing_cache_internals_are_survivable(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spook loads even when it cannot reach the translation cache."""
    monkeypatch.setattr(
        translation_injection, "_async_get_translations_cache", lambda _: object()
    )

    manager = SpookConditionManager(hass)
    await manager.async_inject_condition_translations()

    assert not manager._translations._overrides
