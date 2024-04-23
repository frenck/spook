"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.helpers import issue_registry as ir

from ...entity import SpookEntityDescription
from .entity import RepairsSpookEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


@dataclass(frozen=True, kw_only=True)
class RepairsSpookButtonEntityDescription(
    SpookEntityDescription,
    ButtonEntityDescription,
):
    """Class describing Spook Repairs button entities."""

    ignore: bool


BUTTONS: tuple[RepairsSpookButtonEntityDescription, ...] = (
    RepairsSpookButtonEntityDescription(
        key="ignore_all",
        translation_key="repairs_ignore_all",
        entity_id="button.ignore_all_issues",
        icon="mdi:checkbox-outline",
        entity_category=EntityCategory.CONFIG,
        ignore=True,
    ),
    RepairsSpookButtonEntityDescription(
        key="unignore_all",
        translation_key="repairs_unignore_all",
        entity_id="button.unignore_all_issues",
        icon="mdi:checkbox-blank-outline",
        entity_category=EntityCategory.CONFIG,
        ignore=False,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    _entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook sensor."""
    async_add_entities(RepairsSpookButtonEntity(description) for description in BUTTONS)


class RepairsSpookButtonEntity(RepairsSpookEntity, ButtonEntity):
    """Spook button providing Repairs actions."""

    entity_description: RepairsSpookButtonEntityDescription

    async def async_press(self) -> None:
        """Press the button."""
        issue_registry = ir.async_get(self.hass)
        for domain, issue_id in issue_registry.issues:
            issue_registry.async_ignore(
                domain,
                issue_id,
                ignore=self.entity_description.ignore,
            )
