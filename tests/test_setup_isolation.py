"""Tests for Spook setup failure isolation.

A single repair, service, or ectoplasm that fails to set up must not
prevent the rest of Spook from loading.
"""
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.spook import setup_helpers
from custom_components.spook.repairs import AbstractSpookRepair, SpookRepairManager
from custom_components.spook.services import (
    ReplaceExistingService,
    SpookServiceManager,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    import pytest


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
