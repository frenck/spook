"""Tests for putting Spook's condition strings where the UI looks for them."""

# ruff: noqa: SLF001
# pylint: disable=protected-access
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.websocket_api.commands import (
    _async_get_all_condition_descriptions_json,
)
from homeassistant.helpers.condition import async_get_all_descriptions
from homeassistant.helpers.translation import (
    async_get_cached_translations,
    async_get_translations,
)
from homeassistant.setup import async_setup_component
import pytest  # noqa: TC002

from custom_components.spook import translation_injection
from custom_components.spook.condition import SpookConditionManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_NAME = "component.automation.conditions.triggered_by_user.name"
_FIELD = "component.automation.conditions.triggered_by_user.fields.person.name"
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
    try:
        translations = _automation_conditions(hass)
        assert translations[_NAME] == "Triggered by a user 👻"
        assert translations[_FIELD] == "People"
        assert translations[_NOT_NAME] == "Not triggered by a user 👻"
    finally:
        manager.async_on_unload()


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
    try:
        assert not manager._translations._overrides
    finally:
        manager.async_on_unload()


async def test_the_api_the_frontend_calls_returns_them(hass: HomeAssistant) -> None:
    """The labels reach the automation editor, not just Spook's own cache.

    `frontend/get_translations` is a thin wrapper over
    `async_get_translations`, so calling it the way the websocket handler does
    is the same question the condition picker asks. The automation integration
    is set up first on purpose: loading its own translations is exactly what
    would overwrite Spook's if the injection went in at the wrong moment.
    """
    assert await async_setup_component(hass, "automation", {"automation": []})
    await hass.async_block_till_done()

    manager = SpookConditionManager(hass)
    await manager.async_inject_condition_translations()

    for integration in (["automation"], None):
        resources = await async_get_translations(hass, "en", "conditions", integration)
        assert resources[_NAME] == "Triggered by a user 👻", integration
        assert resources[_NOT_NAME] == "Not triggered by a user 👻", integration
        assert resources[_FIELD] == "People", integration


async def test_descriptors_reach_the_condition_picker(hass: HomeAssistant) -> None:
    """The conditions show up in the automation editor, with their fields.

    Their descriptors cannot live in `conditions.yaml`: hassfest requires
    underscore-slug keys there and these name another domain. Without a
    descriptor the condition still works, but the websocket drops every
    condition whose description is None, so it disappears from the picker
    entirely. This is the test that it does not.
    """
    assert await async_setup_component(hass, "automation", {"automation": []})
    await hass.async_block_till_done()

    manager = SpookConditionManager(hass)
    # The real path: the descriptors are loaded during setup, the same way the
    # service manager loads its own.
    await manager.async_setup()
    try:
        descriptions = await async_get_all_descriptions(hass)
        assert descriptions["automation.triggered_by_user"]["fields"]["person"]
        assert descriptions["automation.not_triggered_by_user"] == {"fields": {}}

        payload = await _async_get_all_condition_descriptions_json(hass)
        assert b"automation.triggered_by_user" in payload
    finally:
        manager.async_on_unload()

    after = await async_get_all_descriptions(hass)
    assert "automation.triggered_by_user" not in after
