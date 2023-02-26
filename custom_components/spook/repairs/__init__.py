"""Spook - Not your homie."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from ..const import DOMAIN, LOGGER


class AbstractSpookRepair(ABC):
    """Abstract base class to hold a Spook repairs."""

    domain: str
    repair: str

    hass: HomeAssistant
    issue_registry: ir.IssueRegistry

    def __init__(self, hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
        """Initialize the service."""
        self.hass = hass
        self.issue_registry = issue_registry

    @final
    @callback
    def _async_create_issue(
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
            translation_key=f"{self.domain}_{self.repair}",
            translation_placeholders=translation_placeholders,
        )

    async def async_activate(self) -> None:
        """Handle the activating a repair."""

    async def async_deactivate(self) -> None:
        """Unregister the repair."""


class AbstractSpookSingleShotRepairs(AbstractSpookRepair, ABC):
    """Abstract class to hold repairs that are single a shot."""

    @abstractmethod
    async def async_inspect(self) -> None:
        """Trigger a single shot repair."""
        raise NotImplementedError

    @final
    async def async_activate(self) -> None:
        """Actives the repairs."""
        await super().async_activate()
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

    async def async_setup(self, entry: ConfigEntry) -> None:
        """Set up the Spook repairs."""
        LOGGER.debug("Setting up Spook repairs")

        # Load all services
        for module_file in Path(__file__).parent.rglob("*.py"):
            if module_file.name == "__init__.py":
                continue
            module = importlib.import_module(f".{module_file.name[:-3]}", __package__)
            await self.async_activate(
                module.SpookRepair(self.hass, self.issue_registry)
            )

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
                    f"{repair.domain}_{repair.repair}"
                ):
                    self.issue_registry.async_remove_issue(domain, issue_id)
