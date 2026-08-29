"""Tests for Spook service translations."""
# ruff: noqa: SLF001
# pylint: disable=protected-access

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from homeassistant.helpers.translation import (
    _async_get_translations_cache,
    async_get_cached_translations,
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
        == "Restart the Home Assistant action."
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
