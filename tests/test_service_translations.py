"""Tests for Spook service translations."""
# ruff: noqa: SLF001
# pylint: disable=protected-access

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from homeassistant.helpers.translation import (
    _async_get_translations_cache,
    async_get_cached_translations,
    async_get_translations,
)

from custom_components.spook import services as spook_services
from custom_components.spook.services import (
    AbstractSpookService,
    SpookServiceManager,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    import pytest

SPOOK_ROOT = Path(__file__).parents[1] / "custom_components" / "spook"


def _given_a_cached_translation(hass: HomeAssistant, key: str, value: str) -> None:
    """Put a Home Assistant translation string in the cache.

    Written by hand rather than loaded, because a Home Assistant installed
    from git has no built translations: those are generated when a release is
    built, so only `strings.json` ships in the repository. Reading core's own
    translations here would tie these tests to how Home Assistant was
    installed rather than to what Spook does with them.
    """
    cache = _async_get_translations_cache(hass).cache_data.cache
    cache.setdefault("en", {}).setdefault("services", {}).setdefault(
        "homeassistant", {}
    )[key] = value


class MockSpookService(AbstractSpookService):
    """Mock Spook service."""

    domain = "homeassistant"
    service = "restart"

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""


def _a_manager_with_restart(hass: HomeAssistant) -> SpookServiceManager:
    """Return a manager carrying Spook's restart action, not set up yet."""
    manager = SpookServiceManager(hass)
    manager._services.add(MockSpookService(hass))
    manager._service_schemas = {"homeassistant_restart": {}}
    return manager


async def test_actions_are_translated_in_a_profile_language(
    hass: HomeAssistant,
) -> None:
    """Test a language other than the server's gets Spook's strings too.

    Everybody picks a language in their own profile, and the frontend asks
    for that one. Spook used to write its strings into the server's language
    only, so a Dutch profile on an English server read core's own. #1820.
    """
    manager = _a_manager_with_restart(hass)
    manager._async_follow_translation_loads()
    await manager.async_inject_service_translations()

    translations = await async_get_translations(
        hass, "nl", "services", {"homeassistant"}
    )

    assert translations["component.homeassistant.services.restart.name"] == (
        "Herstart 👻"
    )
    assert (
        translations["component.homeassistant.services.restart.fields.force.name"]
        == "Forceer herstart"
    )

    # The test harness shares one translation cache between tests, so leave
    # it the way it was found.
    manager.async_clear_service_translation_overrides()
    for undo in manager._on_unload:
        undo()


async def test_unloading_stops_following_translation_loads(
    hass: HomeAssistant,
) -> None:
    """Test unloading leaves Home Assistant's translation cache as it was."""
    cache = _async_get_translations_cache(hass)
    original_class = cache.__class__
    manager = _a_manager_with_restart(hass)
    manager._async_follow_translation_loads()
    assert cache.__class__ is not original_class

    for undo in manager._on_unload:
        undo()

    assert cache.__class__ is original_class
    translations = await async_get_translations(
        hass, "de", "services", {"homeassistant"}
    )
    assert "component.homeassistant.services.restart.fields.force.name" not in (
        translations
    )


async def test_requests_for_a_new_language_all_wait_for_spook(
    hass: HomeAssistant,
) -> None:
    """Test a second request for the same language does not read it halfway."""
    manager = _a_manager_with_restart(hass)
    manager._async_follow_translation_loads()
    await manager.async_inject_service_translations()

    first, second = await asyncio.gather(
        async_get_translations(hass, "nl", "services", {"homeassistant"}),
        async_get_translations(hass, "nl", "services", {"homeassistant"}),
    )

    key = "component.homeassistant.services.restart.name"
    assert first[key] == second[key] == "Herstart 👻"

    manager.async_clear_service_translation_overrides()
    for undo in manager._on_unload:
        undo()


async def test_a_language_that_failed_is_tried_again(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a failed injection does not mark the language as done."""
    manager = _a_manager_with_restart(hass)
    manager._async_follow_translation_loads()
    await manager.async_inject_service_translations()

    original = manager.async_inject_service_translations
    calls = 0

    async def _fails_once(languages: Any = None) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            msg = "boom"
            raise RuntimeError(msg)
        await original(languages)

    monkeypatch.setattr(manager, "async_inject_service_translations", _fails_once)

    await async_get_translations(hass, "nl", "services", {"homeassistant"})
    assert "nl" not in manager._languages

    translations = await async_get_translations(
        hass, "nl", "services", {"homeassistant"}
    )
    assert translations["component.homeassistant.services.restart.name"] == (
        "Herstart 👻"
    )

    manager.async_clear_service_translation_overrides()
    for undo in manager._on_unload:
        undo()


async def test_injecting_everywhere_includes_a_language_under_way(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a reinjection also covers a language still on its first injection."""
    manager = _a_manager_with_restart(hass)
    manager._language_tasks["nl"] = hass.loop.create_future()  # type: ignore[assignment]
    injected: list[str] = []

    async def _record(language: str, *_args: Any) -> None:
        injected.append(language)

    monkeypatch.setattr(manager, "_async_inject_translations_for", _record)

    await manager.async_inject_service_translations()

    assert sorted(injected) == ["en", "nl"]
    manager._language_tasks.clear()


async def test_a_load_that_outlives_unloading_adds_nothing(
    hass: HomeAssistant,
) -> None:
    """Test a load still under way when Spook unloads leaves Spook out."""
    cache = _async_get_translations_cache(hass)
    manager = _a_manager_with_restart(hass)
    manager._async_follow_translation_loads()

    # Unloading turns this off first, while a load can still be under way.
    manager.follows_translation_loads = False
    await cache.async_load("fr", {"homeassistant"})

    assert "fr" not in manager._languages
    assert "fr" not in manager._language_tasks

    for undo in manager._on_unload:
        undo()


async def test_service_translations_are_injected(hass: HomeAssistant) -> None:
    """Test service translation strings are injected for overridden services."""
    service = MockSpookService(hass)
    manager = SpookServiceManager(hass)
    manager._services.add(service)
    manager._service_schemas = {"homeassistant_restart": {}}

    await manager.async_inject_service_translations()

    translations = async_get_cached_translations(
        hass,
        "en",
        "services",
        "homeassistant",
    )
    assert translations["component.homeassistant.services.restart.name"] == "Restart 👻"
    assert (
        translations["component.homeassistant.services.restart.description"]
        == "Restarts Home Assistant."
    )
    assert (
        translations["component.homeassistant.services.restart.fields.safe_mode.name"]
        == "Safe mode"
    )
    assert (
        translations[
            "component.homeassistant.services.restart.fields.safe_mode.description"
        ]
        == "If the restart should be done in safe mode. This will disable all custom integrations and frontend modules."
    )
    assert (
        "en",
        "homeassistant",
        "component.homeassistant.services.restart.fields.force.required",
    ) not in manager._service_translation_overrides

    manager.async_clear_service_translation_overrides()


async def test_service_translation_overrides_are_restored(
    hass: HomeAssistant,
) -> None:
    """Test injected service translation strings are restored."""
    service = MockSpookService(hass)
    manager = SpookServiceManager(hass)
    manager._services.add(service)
    manager._service_schemas = {"homeassistant_restart": {}}

    original_name = "Restart"
    _given_a_cached_translation(
        hass,
        "component.homeassistant.services.restart.name",
        original_name,
    )

    await manager.async_inject_service_translations()
    translations = async_get_cached_translations(
        hass,
        "en",
        "services",
        "homeassistant",
    )
    assert translations["component.homeassistant.services.restart.name"] == "Restart 👻"

    manager.async_clear_service_translation_overrides()

    translations = async_get_cached_translations(
        hass,
        "en",
        "services",
        "homeassistant",
    )
    assert (
        translations["component.homeassistant.services.restart.name"] == original_name
    )


async def test_new_service_translations_are_removed_on_restore(
    hass: HomeAssistant,
) -> None:
    """Test injected translation strings without an original are removed."""
    service = MockSpookService(hass)
    manager = SpookServiceManager(hass)
    manager._services.add(service)
    manager._service_schemas = {"homeassistant_restart": {}}

    await manager.async_inject_service_translations()
    translations = async_get_cached_translations(
        hass,
        "en",
        "services",
        "homeassistant",
    )
    assert (
        translations["component.homeassistant.services.restart.fields.force.name"]
        == "Force restart"
    )

    manager.async_clear_service_translation_overrides()

    translations = async_get_cached_translations(
        hass,
        "en",
        "services",
        "homeassistant",
    )
    assert (
        "component.homeassistant.services.restart.fields.force.name" not in translations
    )


async def test_service_translation_injection_handles_missing_cache(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test service translation injection handles missing cache internals."""
    service = MockSpookService(hass)
    manager = SpookServiceManager(hass)
    manager._services.add(service)
    manager._service_schemas = {"homeassistant_restart": {}}

    monkeypatch.setattr(
        spook_services, "_async_get_translations_cache", lambda _: object()
    )

    await manager.async_inject_service_translations()

    assert not manager._service_translation_overrides


def test_service_translation_restore_handles_missing_cache(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test service translation restore handles missing cache internals."""
    manager = SpookServiceManager(hass)
    manager._service_translation_overrides[
        ("en", "homeassistant", "component.homeassistant.services.restart.name")
    ] = "Restart Home Assistant"

    monkeypatch.setattr(
        spook_services, "_async_get_translations_cache", lambda _: object()
    )

    manager.async_clear_service_translation_overrides()

    assert not manager._service_translation_overrides


def test_service_modules_have_service_translations() -> None:
    """Test every service schema has a matching service translation."""
    service_descriptions = yaml.safe_load((SPOOK_ROOT / "services.yaml").read_text())
    translations = json.loads((SPOOK_ROOT / "translations" / "en.json").read_text())

    assert set(service_descriptions) == set(translations["services"])


def test_service_translation_names_do_not_include_ghost() -> None:
    """Test service translation names do not include Spook's ghost marker."""
    translations = json.loads((SPOOK_ROOT / "translations" / "en.json").read_text())

    assert all(
        "👻" not in service["name"] for service in translations["services"].values()
    )


class MockSpookSelectorService(AbstractSpookService):
    """Mock Spook service in another domain, with a translated selector."""

    domain = "repairs"
    service = "list"

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""


_SEVERITY_SCHEMA = {
    "repairs_list": {
        "fields": {
            "severity": {
                "selector": {"select": {"translation_key": "repair_issue_severity"}}
            }
        }
    }
}


async def test_selector_labels_are_injected_for_the_actions_domain(
    hass: HomeAssistant,
) -> None:
    """Test a selector's option labels are found under the action's domain.

    Home Assistant looks them up under the domain the action is in, and Spook
    keeps them under its own: without this they show as their raw values.
    """
    manager = SpookServiceManager(hass)
    manager._services.add(MockSpookSelectorService(hass))
    manager._service_schemas = _SEVERITY_SCHEMA

    await manager.async_inject_service_translations()

    translations = async_get_cached_translations(hass, "en", "selector", "repairs")
    assert (
        translations[
            "component.repairs.selector.repair_issue_severity.options.critical"
        ]
        == "Critical"
    )

    manager.async_clear_service_translation_overrides()

    translations = async_get_cached_translations(hass, "en", "selector", "repairs")
    assert not any("repair_issue_severity" in key for key in translations)


async def test_selector_labels_already_there_are_put_back(
    hass: HomeAssistant,
) -> None:
    """Test a label the domain had of its own is restored, not removed."""
    key = "component.repairs.selector.repair_issue_severity.options.critical"
    cache = _async_get_translations_cache(hass).cache_data.cache
    cache.setdefault("en", {}).setdefault("selector", {}).setdefault("repairs", {})[
        key
    ] = "Its own"
    manager = SpookServiceManager(hass)
    manager._services.add(MockSpookSelectorService(hass))
    manager._service_schemas = _SEVERITY_SCHEMA

    await manager.async_inject_service_translations()
    assert (
        async_get_cached_translations(hass, "en", "selector", "repairs")[key]
        == "Critical"
    )

    manager.async_clear_service_translation_overrides()

    assert (
        async_get_cached_translations(hass, "en", "selector", "repairs")[key]
        == "Its own"
    )


def test_every_selector_translation_key_is_translated() -> None:
    """Test each selector translation key an action uses has its labels.

    Otherwise the injection has nothing to inject, and the options show as
    their raw values all the same.
    """
    descriptors = yaml.safe_load((SPOOK_ROOT / "services.yaml").read_text())
    translations = json.loads((SPOOK_ROOT / "translations" / "en.json").read_text())
    # Collected per key, as several fields can share one translation key.
    used: dict[str, set[str]] = {}
    for descriptor in descriptors.values():
        for field_schema in ((descriptor or {}).get("fields") or {}).values():
            for selector_config in (
                (field_schema or {}).get("selector") or {}
            ).values():
                if (
                    not isinstance(selector_config, dict)
                    or "translation_key" not in selector_config
                ):
                    continue

                used.setdefault(selector_config["translation_key"], set()).update(
                    option["value"] if isinstance(option, dict) else option
                    for option in selector_config.get("options", [])
                )

    translated = {
        key: set(selector.get("options", {}))
        for key, selector in translations.get("selector", {}).items()
    }

    assert used
    # Every option needs its own label: one that is missing shows as its raw
    # value, even with the rest of the selector translated.
    assert {
        key: options - translated.get(key, set()) for key, options in used.items()
    } == {key: set() for key in used}
