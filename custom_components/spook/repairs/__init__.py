"""Spook - Not your homie."""
from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import final

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
)
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers import (
    entity_registry as er,
)
from homeassistant.helpers import (
    issue_registry as ir,
)
from homeassistant.helpers.debounce import Debouncer

from ..const import DOMAIN, LOGGER


class AbstractSpookRepairBase(ABC):
    """Abstract base class to hold a Spook repairs."""

    domain: str
    repair: str

    hass: HomeAssistant
    issue_registry: ir.IssueRegistry
    area_registry: ar.AreaRegistry
    device_registry: dr.DeviceRegistry
    entity_registry: er.EntityRegistry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service."""
        self.hass = hass
        self.issue_registry = ir.async_get(hass)
        self.area_registry = ar.async_get(hass)
        self.device_registry = dr.async_get(hass)
        self.entity_registry = er.async_get(hass)

    @final
    @callback
    def async_create_issue(
        self,
        *,
        breaks_in_ha_version: str | None = None,
        data: dict[str, str | int | float | None] | None = None,
        is_fixable: bool = False,
        is_persistent: bool = False,
        issue_domain: str | None = None,
        issue_id: str,
        learn_more_url: str | None = None,
        severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Create an issue."""
        ir.async_create_issue(
            self.hass,
            breaks_in_ha_version=breaks_in_ha_version,
            data=data,
            domain=DOMAIN,
            is_fixable=is_fixable,
            is_persistent=is_persistent,
            issue_domain=issue_domain or self.domain,
            issue_id=f"{self.repair}_{issue_id}",
            learn_more_url=learn_more_url,
            severity=severity,
            translation_key=self.repair,
            translation_placeholders=translation_placeholders,
        )

    @final
    @callback
    def async_delete_issue(
        self,
        issue_id: str,
    ) -> None:
        """Remove an issue."""
        ir.async_delete_issue(
            self.hass,
            domain=DOMAIN,
            issue_id=f"{self.repair}_{issue_id}",
        )

    @abstractmethod
    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        raise NotImplementedError

    @abstractmethod
    async def async_inspect(self) -> None:
        """Trigger a repair check."""
        raise NotImplementedError

    @abstractmethod
    async def async_deactivate(self) -> None:
        """Unregister the repair."""
        raise NotImplementedError


class AbstractSpookRepair(AbstractSpookRepairBase):
    """Abstract base class to hold a Spook repairs."""

    inspect_events: set[str] | None = None
    inspect_debouncer: Debouncer
    _event_subs = set[Callable[[], None]]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self._subs = set()

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        # Debouncer to prevent multiple inspections / inspections fired quickly
        # after each other.
        self.inspect_debouncer = Debouncer(
            self.hass,
            LOGGER,
            cooldown=10,
            immediate=False,
            function=self.async_inspect,
        )

        # Spook says: Bounce!
        await self.inspect_debouncer.async_call()

        if self.inspect_events is None:
            return

        for event in self.inspect_events:
            self._event_subs.add(
                self.hass.bus.async_listen(event, self.inspect_debouncer.async_call),
            )

    async def async_deactivate(self) -> None:
        """Unregister the repair."""
        for sub in self._event_subs:
            sub()


class AbstractSpookSingleShotRepairs(AbstractSpookRepairBase, ABC):
    """Abstract class to hold repairs that are single a shot."""

    @final
    async def async_activate(self) -> None:
        """Actives the repairs."""
        await self.async_inspect()

    @final
    async def async_deactivate(self) -> None:
        """Unregister the repair."""


@dataclass
class SpookRepairManager:
    """Class to manage Spook repairs."""

    hass: HomeAssistant

    _repairs: set[AbstractSpookRepair] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Post initialization."""
        self.issue_registry = ir.async_get(self.hass)
        LOGGER.debug("Spook repair manager initialized")

    async def async_setup(self) -> None:
        """Set up the Spook repairs."""
        LOGGER.debug("Setting up Spook repairs")

        # Load all services
        for module_file in Path(__file__).parent.rglob("*.py"):
            if module_file.name == "__init__.py":
                continue
            module = importlib.import_module(f".{module_file.name[:-3]}", __package__)
            await self.async_activate(module.SpookRepair(self.hass))

    async def async_activate(self, repair: AbstractSpookRepair) -> None:
        """Register a Spook repair."""
        LOGGER.debug(
            "Registering Spook repairs: %s.%s",
            repair.domain,
            repair.repair,
        )
        await repair.async_activate()
        self._repairs.add(repair)

    async def async_on_unload(self) -> None:
        """Tear down the Spook reapris."""
        LOGGER.debug("Tearing down Spook repairs")
        for repair in self._repairs:
            LOGGER.debug(
                "Unregistering Spook repair: %s.%s",
                repair.domain,
                repair.repair,
            )
            await repair.async_deactivate()

            # Remove issues created by this Spook repair
            for domain, issue_id in self.issue_registry.issues:
                if domain == DOMAIN and issue_id.startswith(
                    f"{repair.domain}_{repair.repair}",
                ):
                    self.issue_registry.async_delete(domain, issue_id)


async def async_create_fix_flow(
    _hass: HomeAssistant,
    _issue_id: str,
    _data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    return ConfirmRepairFlow()
