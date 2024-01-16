"""Spook - Not your homie."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, final

from homeassistant.components.homeassistant import SERVICE_HOMEASSISTANT_RESTART
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.data_entry_flow import FlowResult


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
    # pylint: disable-next=too-many-arguments
    def async_create_issue(  # noqa: PLR0913
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
    inspect_config_entry_changed: bool | str = False
    inspect_on_reload: bool | str = False
    _event_subs: set[Callable[[], None]]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self._event_subs = set()

    async def async_activate(self) -> None:  # noqa: C901
        """Handle the activating a repair."""

        async def _async_inspect() -> None:
            # Don't inspect if we are stopping
            if self.hass.is_stopping:
                return

            await self.async_inspect()

        # Debouncer to prevent multiple inspections / inspections fired quickly
        # after each other.
        self.inspect_debouncer = Debouncer(
            self.hass,
            LOGGER,
            cooldown=3,
            immediate=False,
            function=_async_inspect,
        )

        # Spook says: Bounce!
        await self.inspect_debouncer.async_call()

        if self.inspect_events is None:
            return

        async def _async_call_inspect_debouncer(_: Event) -> None:
            # Trigger an inspection when an event is received from the event bus.
            await self.inspect_debouncer.async_call()

        for event in self.inspect_events:
            self._event_subs.add(
                self.hass.bus.async_listen(event, _async_call_inspect_debouncer),
            )

        if self.inspect_on_reload:

            @callback
            def _filter_event(event: Event) -> bool:
                """Filter for reload events."""
                service = event.data.get("service")
                if service is None:
                    return False
                if service == "reload_all":
                    return True
                if service != "reload":
                    return False
                if self.inspect_on_reload is True:
                    return True
                if self.inspect_on_reload == event.data.get("domain"):
                    return True
                return False

            self.hass.bus.async_listen(
                "call_service",
                _async_call_inspect_debouncer,
                event_filter=_filter_event,
            )

        if self.inspect_config_entry_changed:

            async def _async_config_entry_changed(
                _hass: HomeAssistant,
                entry: ConfigEntry,
            ) -> None:
                """Handle options update."""
                if (
                    self.inspect_config_entry_changed is not True
                    and entry.domain != self.inspect_config_entry_changed
                ):
                    return
                await self.inspect_debouncer.async_call()

            async_dispatcher_connect(
                self.hass,
                SIGNAL_CONFIG_ENTRY_CHANGED,
                _async_config_entry_changed,
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
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/repairs/*.py"):
            if module_file.name == "__init__.py":
                continue
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace("/", ".")
            module = importlib.import_module(f".{module_path}", __package__)
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


class RestartRequiredFixFlow(RepairsFlow):
    """Handler for a repairs issue flow that restarts Home Assistant."""

    issue_id = "restart_required"

    async def async_step_init(
        self,
        _: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle asking confirmation of restart."""
        return await self.async_step_confirm_restart()

    async def async_step_confirm_restart(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle the confirm of restart."""
        if user_input is not None:
            await self.hass.services.async_call(
                "homeassistant",
                SERVICE_HOMEASSISTANT_RESTART,
            )
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm_restart")


async def async_create_fix_flow(
    _hass: HomeAssistant,
    issue_id: str,
    _data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id == "restart_required":
        return RestartRequiredFixFlow()
    return ConfirmRepairFlow()
