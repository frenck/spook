"""Spook - Your homie."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, final

from homeassistant.components.homeassistant import SERVICE_HOMEASSISTANT_RESTART
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntry,
    ConfigEntryChange,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM
from homeassistant.util.async_ import create_eager_task

from .const import DOMAIN, LOGGER
from .entity_filtering import async_get_all_entity_ids

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping
    from types import ModuleType

    from homeassistant.data_entry_flow import FlowResult
    from homeassistant.helpers.entity_platform import EntityPlatform
    from homeassistant.util.event_type import EventType


class AbstractSpookRepairBase(ABC):
    """Abstract base class to hold a Spook repairs."""

    domain: str
    repair: str

    hass: HomeAssistant
    issue_registry: ir.IssueRegistry
    area_registry: ar.AreaRegistry
    device_registry: dr.DeviceRegistry
    entity_registry: er.EntityRegistry

    issue_ids: set[str]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service."""
        self.hass = hass
        self.issue_registry = ir.async_get(hass)
        self.area_registry = ar.async_get(hass)
        self.device_registry = dr.async_get(hass)
        self.entity_registry = er.async_get(hass)
        self.issue_ids = set()

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
        self.issue_ids.add(issue_id)
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
        self.issue_ids.discard(issue_id)
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

    async def async_deactivate(self) -> None:
        """Unregister the repair."""
        for issue_id in self.issue_ids:
            self.async_delete_issue(issue_id)


class AbstractSpookRepair(AbstractSpookRepairBase):
    """Abstract base class to hold a Spook repairs."""

    inspect_events: set[EventType[Any] | str] | None = None
    inspect_debouncer: Debouncer[Coroutine[Any, Any, None]]
    inspect_config_entry_changed: bool | str = False
    inspect_on_reload: bool | str = False

    automatically_clean_up_issues: bool = False
    possible_issue_ids: set[str]

    _event_subs: set[Callable[[], None]]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the repair."""
        super().__init__(hass)
        self._event_subs = set()
        self.possible_issue_ids = set()

    async def async_activate(self) -> None:  # noqa: C901
        """Handle the activating a repair."""

        async def _async_inspect() -> None:
            # Don't inspect if we are stopping
            if self.hass.is_stopping:
                return

            if self.automatically_clean_up_issues:
                # Reset registered issues. If they are still valid, they will be
                # re-registered during the inspection.
                self.issue_ids.clear()

            await self.async_inspect()

            if self.automatically_clean_up_issues:
                # Remove issues that are not longer created after inspection.
                for issue_id in self.possible_issue_ids - self.issue_ids:
                    self.async_delete_issue(issue_id)
                # Remove issues that are no longer valid.
                for issue_id in self.issue_ids - self.possible_issue_ids:
                    self.async_delete_issue(issue_id)

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
            def _filter_event(data: Mapping[str, Any] | Event) -> bool:
                """Filter for reload events."""
                event_data = data.data if isinstance(data, Event) else data
                service = event_data.get("service")
                if service is None:
                    return False
                if service == "reload_all":
                    return True
                if service != "reload":
                    return False
                if self.inspect_on_reload is True:
                    return True
                return self.inspect_on_reload == event_data.get("domain")

            self.hass.bus.async_listen(
                "call_service",
                _async_call_inspect_debouncer,
                event_filter=_filter_event,
            )

        if self.inspect_config_entry_changed:

            async def _async_config_entry_changed(  # pylint: disable=unused-argument
                change: ConfigEntryChange,  # noqa: ARG001
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
        await super().async_deactivate()


class AbstractSpookEntityComponentUnknownReferencesRepair(AbstractSpookRepair, ABC):
    """Base class for repairs that find unknown references in component entities.

    Handles the shared boilerplate for inspecting entities loaded via
    `EntityComponent` (e.g. automations, scripts): iterating the component's
    entities, skipping unavailable ones, computing per-entity unknown references
    via a subclass hook, and creating an issue with the standard translation
    placeholders (``<reference_label>``, ``<entity_label>``, ``edit``,
    ``entity_id``).
    """

    automatically_clean_up_issues = True

    #: Entity class representing an unavailable/broken instance. Entities of
    #: this type are still tracked in ``possible_issue_ids`` but skipped during
    #: issue creation.
    unavailable_entity_class: type

    #: Translation placeholder key holding the entity's display name (e.g.
    #: ``"automation"`` or ``"script"``).
    entity_label: str

    #: Translation placeholder key holding the bulleted list of unknown
    #: references (e.g. ``"areas"``, ``"floors"``, ``"entities"``).
    reference_label: str

    #: Format string used to build the ``edit`` placeholder. Must contain a
    #: ``{unique_id}`` field (e.g. ``"/config/automation/edit/{unique_id}"``).
    edit_url_pattern: str

    async def _async_setup_inspection(self) -> None:
        """Prepare per-inspection state (called once per inspection cycle).

        Override to cache lookups (e.g. known IDs from a registry) on ``self``
        for use during per-entity inspection.
        """

    # pylint: disable-next=unused-argument
    def _should_inspect_entity(self, entity: Any) -> bool:  # noqa: ARG002
        """Decide whether the given entity should be inspected.

        Defaults to inspecting every entity. Override (e.g. to skip disabled
        entities) when needed.
        """
        return True

    @abstractmethod
    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return the set of unknown referenced IDs for a single entity."""

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        self.possible_issue_ids.clear()

        if self.domain not in (instances := self.hass.data.get(DATA_INSTANCES, {})):
            return

        entity_component = instances[self.domain]

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        await self._async_setup_inspection()

        for entity in entity_component.entities:
            self.possible_issue_ids.add(entity.entity_id)

            if isinstance(entity, self.unavailable_entity_class):
                continue

            if not self._should_inspect_entity(entity):
                continue

            unknown = await self._async_compute_unknown_references(entity)
            if not unknown:
                continue

            sorted_unknown = sorted(unknown)

            self.async_create_issue(
                issue_id=entity.entity_id,
                translation_placeholders={
                    self.reference_label: "\n".join(
                        f"- `{item}`" for item in sorted_unknown
                    ),
                    self.entity_label: entity.name,
                    "edit": self.edit_url_pattern.format(unique_id=entity.unique_id),
                    "entity_id": entity.entity_id,
                },
            )
            LOGGER.debug(
                "Spook found unknown %s in %s and created an issue for it; %s: %s",
                self.reference_label,
                entity.entity_id,
                self.reference_label.capitalize(),
                ", ".join(sorted_unknown),
            )


class AbstractSpookEntityPlatformUnknownSourceRepair(AbstractSpookRepair, ABC):
    """Base class for repairs that find unknown source entities on helpers.

    Handles the shared boilerplate for inspecting entities loaded via
    `EntityPlatform` (e.g. ``switch_as_x``, ``integration``, ``utility_meter``,
    ``trend``): walking the platforms, optionally filtering by platform domain,
    pulling each entity's source attribute via a subclass hook, and raising an
    issue when the source is no longer known to Home Assistant.
    """

    automatically_clean_up_issues = True

    #: When set, only entities living on platforms whose ``domain`` equals this
    #: value are inspected. ``None`` (the default) inspects every platform of
    #: the integration domain.
    source_platform_domain: str | None = None

    @abstractmethod
    def _get_source_entity_id(self, entity: Any) -> str:
        """Return the source entity ID for the given helper entity."""

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        self.possible_issue_ids.clear()

        LOGGER.debug("Spook is inspecting: %s", self.repair)

        platforms: list[EntityPlatform] | None
        if not (
            platforms := self.hass.data.get(DATA_ENTITY_PLATFORM, {}).get(self.domain)
        ):
            return  # Nothing to do, integration is not loaded.

        known_entity_ids = async_get_all_entity_ids(self.hass)

        for platform in platforms:
            if (
                self.source_platform_domain is not None
                and platform.domain != self.source_platform_domain
            ):
                continue

            for entity in platform.entities.values():
                self.possible_issue_ids.add(entity.entity_id)
                source = self._get_source_entity_id(entity)
                if source not in known_entity_ids:
                    self.async_create_issue(
                        issue_id=entity.entity_id,
                        translation_placeholders={
                            "entity_id": entity.entity_id,
                            "helper": entity.name,
                            "source": source,
                        },
                    )
                    LOGGER.debug(
                        "Spook found unknown source entity %s in %s "
                        "and created an issue for it",
                        source,
                        entity.entity_id,
                    )


class AbstractSpookSingleShotRepairs(AbstractSpookRepairBase, ABC):
    """Abstract class to hold repairs that are single a shot."""

    @final
    async def async_activate(self) -> None:
        """Actives the repairs."""
        await self.async_inspect()

    @final
    async def async_deactivate(self) -> None:
        """Unregister the repair."""
        await super().async_deactivate()


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

        modules: list[ModuleType] = []

        def _load_all_repair_modules() -> None:
            """Load all repair modules."""
            for module_file in Path(__file__).parent.rglob("ectoplasms/*/repairs/*.py"):
                if module_file.name == "__init__.py":
                    continue
                module_path = str(module_file.relative_to(Path(__file__).parent))[
                    :-3
                ].replace("/", ".")
                modules.append(importlib.import_module(f".{module_path}", __package__))

        await self.hass.async_add_import_executor_job(_load_all_repair_modules)
        await asyncio.gather(
            *(
                create_eager_task(self.async_activate(module.SpookRepair(self.hass)))
                for module in modules
            )
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
