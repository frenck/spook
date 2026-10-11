"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import script
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)

from ....icon_checking import (
    async_get_mdi_icons,
    async_icon_fields,
    async_suggest,
    icons_in_actions,
)
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from typing import Any

    from ....icon_checking import MdiIcons


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair finds icons in scripts that do not exist.

    The icon of the script itself, and the icons its actions hand out, like
    `group.set` does. An `mdi:` icon that is not in the Material Design
    Icons set is drawn as an empty spot, without a word.
    """

    domain = script.DOMAIN
    repair = "script_unknown_icons"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True

    unavailable_entity_class = script.UnavailableScriptEntity
    entity_label = "script"
    reference_label = "icons"
    edit_url_pattern = "/config/script/edit/{unique_id}"

    _icons: MdiIcons | None
    _icon_fields: dict[str, frozenset[str]]

    async def _async_setup_inspection(self) -> None:
        """Read the icons and the actions taking one, for this round."""
        self._icons = await async_get_mdi_icons(self.hass)
        self._icon_fields = {}
        if self._icons is not None:
            self._icon_fields = await async_icon_fields(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return the unknown icons of ``entity`` and of its actions."""
        if (icons := self._icons) is None or not isinstance(
            config := entity.raw_config, dict
        ):
            return set()

        found = icons_in_actions(config.get("sequence"), self._icon_fields)
        if isinstance(own_icon := config.get("icon"), str):
            found.add(own_icon)

        unknown = {icon for icon in found if icons.unknown_name(icon) is not None}
        await async_suggest(self.hass, icons, unknown)
        return unknown

    def _format_references(self, references: list[str]) -> str:
        """Return the unknown icons, each with its likely meaning."""
        if (icons := self._icons) is None:
            return super()._format_references(references)
        return "\n".join(f"- {icons.describe(icon)}" for icon in references)
