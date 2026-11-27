"""Tests for Spook setup failure isolation.

A single repair, service, or ectoplasm that fails to set up must not
prevent the rest of Spook from loading.
"""
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_mock_service

from custom_components.spook import condition, setup_helpers, trigger
from custom_components.spook.const import DOMAIN, PLATFORMS
from custom_components.spook.repairs import AbstractSpookRepair, SpookRepairManager
from custom_components.spook.services import (
    ReplaceExistingService,
    SpookServiceManager,
)

if TYPE_CHECKING:
    from types import ModuleType

    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant


class _WorkingRepair(AbstractSpookRepair):
    """Repair that activates fine."""

    domain = "mock"
    repair = "mock_working_repair"

    async def async_inspect(self) -> None:
        """Inspect the repair."""


class _ExplodingConstructor:  # pylint: disable=too-few-public-methods
    """Stand-in repair or service that explodes on construction."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        del hass
        msg = "Boo! This one is haunted"
        raise RuntimeError(msg)


async def test_broken_repair_module_does_not_abort_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a repair failing to set up is skipped and logged."""
    manager = SpookRepairManager(hass)

    broken = SimpleNamespace(
        __name__="mock.broken_repair", SpookRepair=_ExplodingConstructor
    )
    working = SimpleNamespace(
        __name__="mock.working_repair", SpookRepair=_WorkingRepair
    )

    await manager._async_setup_repair_module(broken)
    await manager._async_setup_repair_module(working)

    assert len(manager._repairs) == 1
    assert "mock.broken_repair failed to set up" in caplog.text
    assert "Boo! This one is haunted" in caplog.text

    await manager.async_on_unload()


async def test_broken_ectoplasm_does_not_abort_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an ectoplasm failing to set up is skipped and logged."""

    async def _boom(*_args: Any) -> None:
        msg = "Boo! This one is haunted"
        raise RuntimeError(msg)

    module = SimpleNamespace(__name__="mock.broken_ectoplasm", async_setup_entry=_boom)

    await setup_helpers._async_setup_ectoplasm(hass, SimpleNamespace(), module)

    assert "mock.broken_ectoplasm failed to set up" in caplog.text


async def test_broken_ectoplasm_platform_does_not_abort_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an ectoplasm platform failing to set up is skipped and logged."""

    async def _boom(*_args: Any) -> None:
        msg = "Boo! This one is haunted"
        raise RuntimeError(msg)

    module = SimpleNamespace(__name__="mock.broken_platform", async_setup_entry=_boom)

    await setup_helpers._async_setup_ectoplasm_platform(
        hass,
        SimpleNamespace(),
        lambda *_: None,
        module,
    )

    assert "mock.broken_platform failed to set up" in caplog.text


async def test_broken_service_module_does_not_abort_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a service failing to set up is skipped and logged."""
    manager = SpookServiceManager(hass)

    module = SimpleNamespace(
        __name__="mock.broken_service", SpookService=_ExplodingConstructor
    )

    manager._async_setup_service_module(module)

    assert not manager._services
    assert "mock.broken_service failed to set up" in caplog.text


class _BrokenOverrideService(ReplaceExistingService):
    """Service override that explodes during registration."""

    domain = "light"
    service = "turn_on"

    def async_register(self) -> None:
        """Register the service."""
        msg = "Boo! This one is haunted"
        raise RuntimeError(msg)


async def test_failed_service_override_restores_original_service(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing service override restores the original service.

    When the service to override was already unregistered but the
    replacement fails to register, the original must be put back instead
    of silently disappearing until the next restart.
    """
    async_mock_service(hass, "light", "turn_on")
    manager = SpookServiceManager(hass)

    module = SimpleNamespace(
        __name__="mock.broken_override",
        SpookService=_BrokenOverrideService,
    )

    manager._async_setup_service_module(module)

    assert hass.services.has_service("light", "turn_on")
    assert "mock.broken_override failed to set up" in caplog.text


def _failing_to_import(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    error: Exception,
) -> None:
    """Make importing one module raise, as if Home Assistant moved something.

    Everything else imports as it always does. Modules imported before are
    cached, so the one that fails is the only one doing anything different.
    """
    import_module = importlib.import_module

    def _import_module(name: str, package: str | None = None) -> ModuleType:
        if name.removeprefix(".").endswith(module_name):
            raise error
        return import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _import_module)


async def _async_set_up_repair_modules(hass: HomeAssistant) -> set[str]:
    """Set up every Spook repair, and return the modules that made it."""
    manager = SpookRepairManager(hass)
    await manager.async_setup()
    set_up = {type(repair).__module__ for repair in manager._repairs}
    await manager.async_on_unload()
    return set_up


@pytest.mark.parametrize(
    "error",
    [
        ImportError("cannot import name 'gone' from 'homeassistant.helpers'"),
        AttributeError("module 'homeassistant.const' has no attribute 'GONE'"),
    ],
)
async def test_repair_module_failing_to_import_does_not_abort_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    """Test a repair that fails to import is skipped, and the others set up.

    The realistic cause is Home Assistant moving or renaming something a
    repair imports. That is one repair broken, not all of them.
    """
    # The Lovelace repair needs the Lovelace data container to activate.
    hass.data["lovelace"] = SimpleNamespace(dashboards={}, resources=None)

    broken = (
        "custom_components.spook.ectoplasms.scene.repairs.unknown_entity_references"
    )
    sibling = "custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references"

    everything = await _async_set_up_repair_modules(hass)
    assert {broken, sibling} <= everything

    _failing_to_import(
        monkeypatch, broken.removeprefix("custom_components.spook."), error
    )
    survivors = await _async_set_up_repair_modules(hass)

    assert survivors == everything - {broken}
    assert f"Spook repair {broken} failed to load and has been skipped" in caplog.text
    assert str(error) in caplog.text


async def _async_set_up_service_modules(hass: HomeAssistant) -> set[str]:
    """Set up every Spook service, and return the modules that made it."""
    manager = SpookServiceManager(hass)
    await manager.async_setup()
    set_up = {type(service).__module__ for service in manager._services}
    manager.async_on_unload()
    return set_up


async def test_service_module_failing_to_import_does_not_abort_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a service that fails to import is skipped, and the others set up.

    Picked from the spook domain, as that one is always there to register on.
    """
    broken = "custom_components.spook.ectoplasms.spook.services.boo"
    sibling = "custom_components.spook.ectoplasms.spook.services.random_fail"

    everything = await _async_set_up_service_modules(hass)
    assert {broken, sibling} <= everything

    _failing_to_import(
        monkeypatch,
        broken.removeprefix("custom_components.spook."),
        ImportError("cannot import name 'gone' from 'homeassistant.helpers'"),
    )
    manager = SpookServiceManager(hass)
    await manager.async_setup()

    survivors = {type(service).__module__ for service in manager._services}
    assert survivors == everything - {broken}
    assert not hass.services.has_service(DOMAIN, "boo")
    assert hass.services.has_service(DOMAIN, "random_fail")
    assert f"Spook service {broken} failed to load and has been skipped" in caplog.text

    manager.async_on_unload()


async def _async_forward_to_ectoplasms(
    hass: HomeAssistant,
) -> dict[Platform, list[str] | Exception]:
    """Forward the setup to every ectoplasm, and return what each platform got."""
    await setup_helpers.async_forward_setup_entry(hass, MockConfigEntry(domain=DOMAIN))
    platform_modules = hass.data.pop(setup_helpers.DATA_ECTOPLASM_PLATFORMS)
    return {
        platform: (
            modules
            if isinstance(modules, Exception)
            else [module.__name__ for module in modules]
        )
        for platform, modules in platform_modules.items()
    }


async def test_ectoplasm_failing_to_import_does_not_abort_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an ectoplasm that fails to import is skipped, and the rest loads.

    The zone ectoplasm brings no platform of its own, so every platform is
    expected to get exactly what it gets without the failure.
    """
    broken = "custom_components.spook.ectoplasms.zone.__init__"

    everything = await _async_forward_to_ectoplasms(hass)
    assert set(everything) == set(PLATFORMS)
    assert all(isinstance(modules, list) for modules in everything.values())

    _failing_to_import(
        monkeypatch,
        broken.removeprefix("custom_components.spook."),
        ImportError("cannot import name 'gone' from 'homeassistant.helpers'"),
    )
    survivors = await _async_forward_to_ectoplasms(hass)

    assert survivors == everything
    assert f"Spook ectoplasm {broken} failed to load and has been skipped" in (
        caplog.text
    )


async def _async_get_trigger_modules(hass: HomeAssistant) -> set[str]:
    """Ask for the Spook triggers afresh, and return the modules they came from."""
    hass.data.pop(trigger.DATA_TRIGGERS, None)
    triggers = await trigger.async_get_triggers(hass)
    return {spook_trigger.__module__ for spook_trigger in triggers.values()}


async def test_trigger_module_failing_to_import_leaves_the_others(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a trigger that fails to import is skipped, and the others are there.

    Home Assistant asks for these while validating automations, and only
    expects an invalid configuration there. Anything else raised takes down
    the validation of every automation, not only the ones using this trigger.
    """
    broken = "custom_components.spook.ectoplasms.spook.triggers.cron"

    everything = await _async_get_trigger_modules(hass)
    assert broken in everything

    _failing_to_import(
        monkeypatch,
        broken.removeprefix("custom_components.spook."),
        ImportError("cannot import name 'gone' from 'homeassistant.helpers'"),
    )
    survivors = await _async_get_trigger_modules(hass)

    assert survivors == everything - {broken}
    assert f"Spook trigger {broken} failed to load and has been skipped" in (
        caplog.text
    )


async def _async_get_condition_modules(hass: HomeAssistant) -> set[str]:
    """Ask for the Spook conditions afresh, and return the modules they came from."""
    hass.data.pop(condition.DATA_CONDITIONS, None)
    conditions = await condition.async_get_conditions(hass)
    return {spook_condition.__module__ for spook_condition in conditions.values()}


async def test_condition_module_failing_to_import_leaves_the_others(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a condition that fails to import is skipped, and the others are there.

    Home Assistant asks for these while validating automations, and only
    expects an invalid configuration there. Anything else raised takes down
    the validation of every automation, not only the ones using this condition.
    """
    broken = "custom_components.spook.ectoplasms.spook.conditions.chance"

    everything = await _async_get_condition_modules(hass)
    assert broken in everything

    _failing_to_import(
        monkeypatch,
        broken.removeprefix("custom_components.spook."),
        ImportError("cannot import name 'gone' from 'homeassistant.helpers'"),
    )
    survivors = await _async_get_condition_modules(hass)

    assert survivors == everything - {broken}
    assert f"Spook condition {broken} failed to load and has been skipped" in (
        caplog.text
    )
