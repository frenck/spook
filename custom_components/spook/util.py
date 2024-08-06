"""Spook - Your homie."""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    CONF_CHOOSE,
    CONF_DEFAULT,
    CONF_ELSE,
    CONF_ENABLED,
    CONF_PARALLEL,
    CONF_REPEAT,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_THEN,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
)
from homeassistant.core import callback, valid_entity_id
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.helpers.template import Template

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from types import ModuleType

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_forward_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Set up Spook ectoplasms."""
    LOGGER.debug("Setting up Spook ectoplasms")

    modules: list[ModuleType] = []

    def _load_all_ectoplasm_modules() -> None:
        """Load all Spook ectoplasm modules."""
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/__init__.py"):
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace(
                "/",
                ".",
            )
            LOGGER.debug("Loading Spook ectoplasm: %s", module_path)
            module = importlib.import_module(f".{module_path}", __package__)
            if hasattr(module, "async_setup_entry"):
                modules.append(module)
                LOGGER.debug("Setting up Spook ectoplasm: %s", module_path)

    await hass.async_add_import_executor_job(_load_all_ectoplasm_modules)
    await asyncio.gather(*(module.async_setup_entry(hass, entry) for module in modules))


async def async_forward_platform_entry_setups_to_ectoplasm(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform: Platform,
) -> None:
    """Set up Spook ectoplasm platform."""
    LOGGER.debug("Setting up Spook ectoplasm platform: %s", platform)

    modules: list[ModuleType] = []

    def _load_all_ectoplasm_platform_modules() -> None:
        """Load all Spook ectoplasm platform modules."""
        for module_file in Path(__file__).parent.rglob(f"ectoplasms/*/{platform}.py"):
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace(
                "/",
                ".",
            )
            LOGGER.debug("Loading Spook %s from ectoplasm: %s", platform, module_path)
            modules.append(importlib.import_module(f".{module_path}", __package__))
            LOGGER.debug("Setting up Spook ectoplasm %s: %s", platform, module_path)

    await hass.async_add_import_executor_job(_load_all_ectoplasm_platform_modules)
    await asyncio.gather(
        *(
            module.async_setup_entry(hass, entry, async_add_entities)
            for module in modules
        )
    )


def link_sub_integrations(hass: HomeAssistant) -> bool:
    """Link Spook sub integrations."""
    LOGGER.debug("Linking up Spook sub integrations")

    changes = False
    for manifest in Path(__file__).parent.rglob("integrations/*/manifest.json"):
        LOGGER.debug("Linking Spook sub integration: %s", manifest.parent.name)
        dest = Path(hass.config.config_dir) / "custom_components" / manifest.parent.name
        if not dest.exists():
            src = (
                Path(hass.config.config_dir)
                / "custom_components"
                / DOMAIN
                / "integrations"
                / manifest.parent.name
            )
            dest.symlink_to(src)
            changes = True
    return changes


def unlink_sub_integrations(hass: HomeAssistant) -> None:
    """Unlink Spook sub integrations."""
    LOGGER.debug("Unlinking Spook sub integrations")
    for manifest in Path(__file__).parent.rglob("integrations/*/manifest.json"):
        LOGGER.debug("Unlinking Spook sub integration: %s", manifest.parent.name)
        dest = Path(hass.config.config_dir) / "custom_components" / manifest.parent.name
        if dest.exists():
            dest.unlink()


@callback
def async_ensure_template_environments_exists(hass: HomeAssistant) -> None:
    """Ensure default template environments exist.

    Spook wants to patch the template environment to allow for custom filters.
    To make this easier, we need to ensure the default template environments
    exist before we patch them.
    """
    if "template.environment" not in hass.data:
        template = Template("OMG Puppies!", hass)
        # pylint: disable-next=protected-access
        assert template._env  # noqa: SLF001, S101

    if "template.environment_limited" not in hass.data:
        template = Template("OMG Puppies!", hass)
        # pylint: disable-next=protected-access
        template._limited = True  # noqa: SLF001
        # pylint: disable-next=protected-access
        assert template._env  # noqa: SLF001, S101

    if "template.environment_strict" not in hass.data:
        template = Template("OMG Puppies!", hass)
        # pylint: disable-next=protected-access
        template._strict = True  # noqa: SLF001
        # pylint: disable-next=protected-access
        assert template._env  # noqa: SLF001, S101


@callback
def async_get_all_area_ids(hass: HomeAssistant) -> set[str]:
    """Return all area IDs, known to Home Assistant."""
    area_registry = ar.async_get(hass)
    return set(area_registry.areas)


@callback
def async_filter_known_area_ids(
    hass: HomeAssistant, *, area_ids: set[str], known_area_ids: set[str] | None = None
) -> set[str]:
    """Filter out known area IDs."""
    if known_area_ids is None:
        known_area_ids = async_get_all_area_ids(hass)
    return {
        area_id for area_id in area_ids - known_area_ids if isinstance(area_id, str)
    }


@callback
def async_get_all_device_ids(hass: HomeAssistant) -> set[str]:
    """Return all device IDs, known to Home Assistant."""
    device_registry = dr.async_get(hass)
    return {device.id for device in device_registry.devices.values()}


@callback
def async_filter_known_device_ids(
    hass: HomeAssistant,
    *,
    device_ids: set[str],
    known_device_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known device IDs."""
    if known_device_ids is None:
        known_device_ids = async_get_all_device_ids(hass)
    return {
        device_id
        for device_id in device_ids - known_device_ids
        if device_id and isinstance(device_id, str)
    }


@callback
def async_get_all_entity_ids(
    hass: HomeAssistant, *, include_all_none: bool = False
) -> set[str]:
    """Return all entity IDs, known to Home Assistant."""
    entity_registry = er.async_get(hass)

    entity_ids = {
        entity.entity_id for entity in entity_registry.entities.values()
    }.union(hass.states.async_entity_ids())

    if include_all_none:
        return entity_ids.union({ENTITY_MATCH_ALL, ENTITY_MATCH_NONE})

    return entity_ids


@callback
def async_filter_known_entity_ids(
    hass: HomeAssistant,
    entity_ids: Iterable[str],
    known_entity_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known entity IDs."""
    if known_entity_ids is None:
        known_entity_ids = async_get_all_entity_ids(hass)

    return {
        entity_id
        for entity_id in entity_ids
        if (
            isinstance(entity_id, str)
            and not entity_id.startswith(
                (
                    "device_tracker.",
                    "group.",
                    "persistent_notification.",
                    "scene.",
                ),
            )
            and entity_id not in known_entity_ids
            and valid_entity_id(entity_id)
        )
    }


@callback
def async_get_all_floor_ids(hass: HomeAssistant) -> set[str]:
    """Return all floor IDs, known to Home Assistant."""
    floor_registry = fr.async_get(hass)
    return {floor.floor_id for floor in floor_registry.floors.values()}


@callback
def async_filter_known_floor_ids(
    hass: HomeAssistant,
    *,
    floor_ids: set[str],
    known_floor_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known floor IDs."""
    if known_floor_ids is None:
        known_floor_ids = async_get_all_label_ids(hass)
    return {
        floor_id
        for floor_id in floor_ids - known_floor_ids
        if floor_id and isinstance(floor_id, str)
    }


@callback
def async_get_all_label_ids(hass: HomeAssistant) -> set[str]:
    """Return all label IDs, known to Home Assistant."""
    label_registry = lr.async_get(hass)
    return {label.label_id for label in label_registry.labels.values()}


@callback
def async_filter_known_label_ids(
    hass: HomeAssistant,
    *,
    label_ids: set[str],
    known_label_ids: set[str] | None = None,
) -> set[str]:
    """Filter out known label IDs."""
    if known_label_ids is None:
        known_label_ids = async_get_all_label_ids(hass)
    return {
        label_id
        for label_id in label_ids - known_label_ids
        if label_id and isinstance(label_id, str)
    }


@callback
def async_get_all_services(hass: HomeAssistant) -> set[str]:
    """Return all services, known to Home Assistant."""
    return {
        f"{domain}.{service}"
        for domain, services in hass.services.async_services().items()
        for service in services
    }


@callback
def async_filter_known_services(
    hass: HomeAssistant, *, services: set[str], known_services: set[str] | None = None
) -> set[str]:
    """Filter out known services."""
    if known_services is None:
        known_services = async_get_all_services(hass)
    return {
        service.lower()
        for service in services - known_services
        if isinstance(service, str) and service
    }


@callback
def async_find_services_in_sequence(  # noqa: C901
    sequence: Sequence[dict[str, Any]],
) -> set[str]:
    """Find all services called in a sequence."""
    called_services: set[str] = set()
    for step in sequence:
        action = cv.determine_script_action(step)

        if (
            action == cv.SCRIPT_ACTION_CALL_SERVICE
            and CONF_SERVICE in step
            and step.get(CONF_ENABLED, True)
        ):
            called_services.add(step[CONF_SERVICE])

        if (
            action == cv.SCRIPT_ACTION_CALL_SERVICE
            and "action" in step
            and step.get(CONF_ENABLED, True)
        ):
            called_services.add(step["action"])

        if action == cv.SCRIPT_ACTION_CHOOSE:
            for choice in step[CONF_CHOOSE]:
                called_services |= async_find_services_in_sequence(
                    choice[CONF_SEQUENCE]
                )
            if nested_sequence := step.get(CONF_DEFAULT):
                called_services |= async_find_services_in_sequence(nested_sequence)

        if action == cv.SCRIPT_ACTION_IF:
            called_services |= async_find_services_in_sequence(step[CONF_THEN])
            if nested_sequence := step.get(CONF_ELSE):
                called_services |= async_find_services_in_sequence(nested_sequence)

        if action == cv.SCRIPT_ACTION_PARALLEL:
            for nested_sequence in step[CONF_PARALLEL]:
                called_services |= async_find_services_in_sequence(
                    nested_sequence[CONF_SEQUENCE]
                )

        if action == cv.SCRIPT_ACTION_REPEAT:
            called_services |= async_find_services_in_sequence(
                step[CONF_REPEAT][CONF_SEQUENCE]
            )

    return called_services
