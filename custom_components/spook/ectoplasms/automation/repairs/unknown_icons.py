"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)

from ....icon_checking import (
    async_icon_fields,
    async_require_mdi_icons,
    async_suggest,
    icons_in_actions,
)
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from typing import Any

    from ....icon_checking import MdiIcons


class SpookRepair(AbstractSpookAutomationReferencesRepair):
    """Spook repair finds icons automations hand out that do not exist.

    An action that takes an icon, like `group.set`, sets whatever it is
    given. An `mdi:` icon that is not in the Material Design Icons set is
    drawn as an empty spot, without a word.
    """

    domain = automation.DOMAIN
    repair = "automation_unknown_icons"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        EVENT_COMPONENT_LOADED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
    }
    inspect_config_entry_changed = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "icons"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    _icons: MdiIcons
    _icon_fields: dict[str, frozenset[str]]

    async def _async_setup_inspection(self) -> None:
        """Read the icons and the actions taking one, for this round."""
        self._icons = await async_require_mdi_icons(self.hass)
        self._icon_fields = await async_icon_fields(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return the unknown icons the actions of ``entity`` hand out."""
        if not isinstance(config := entity.raw_config, dict):
            return set()

        icons = self._icons

        actions = config.get("actions", config.get("action"))
        unknown = {
            icon
            for icon in icons_in_actions(actions, self._icon_fields)
            if icons.unknown_name(icon) is not None
        }
        await async_suggest(self.hass, icons, unknown)
        return unknown

    def _format_references(self, references: list[str]) -> str:
        """Return the unknown icons, each with its likely meaning."""
        return "\n".join(f"- {self._icons.describe(icon)}" for icon in references)
