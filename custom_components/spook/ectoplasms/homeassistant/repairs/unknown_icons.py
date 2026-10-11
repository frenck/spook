"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import callback
from homeassistant.core_config import DATA_CUSTOMIZE
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.helpers.entity_component import DATA_INSTANCES

from ....const import LOGGER
from ....icon_checking import async_get_mdi_icons, async_suggest
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from homeassistant.core import Event

    from ....icon_checking import MdiIcons

# Helpers that keep an icon in their own settings, whether made in the UI or
# in YAML. Each hands it out as its entity's own icon.
_HELPER_DOMAINS = frozenset(
    {
        "counter",
        "input_boolean",
        "input_button",
        "input_datetime",
        "input_number",
        "input_select",
        "input_text",
        "schedule",
        "timer",
    }
)

# Zones keep one the same way, but are made under areas, not helpers.
_ZONE_DOMAIN = "zone"


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds icons in settings that the frontend does not have.

    An `mdi:` icon that is not in the Material Design Icons set is drawn as
    an empty spot, without a word. The settings that can hold one are looked
    at together and reported in one issue, each line saying where: an entity,
    a helper, a zone, an area, a floor, a label, a category or `customize:`.
    """

    domain = "homeassistant"
    repair = "unknown_icons"
    inspect_events = {
        EVENT_HOMEASSISTANT_STARTED,
        EVENT_COMPONENT_LOADED,
        EVENT_CORE_CONFIG_UPDATE,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
        fr.EVENT_FLOOR_REGISTRY_UPDATED,
        lr.EVENT_LABEL_REGISTRY_UPDATED,
        cr.EVENT_CATEGORY_REGISTRY_UPDATED,
    }
    inspect_on_reload = True
    automatically_clean_up_issues = True

    async def async_activate(self) -> None:
        """Look again when a helper or zone gets another icon.

        Changing one in the UI, or reloading its YAML, changes the entity and
        nothing else: no registry hears about it.
        """
        await super().async_activate()

        domains = _HELPER_DOMAINS | {_ZONE_DOMAIN}

        @callback
        def _icon_changed(event_data: Mapping[str, Any]) -> bool:
            """Return whether a helper or zone came, went or changed its icon."""
            if event_data["entity_id"].partition(".")[0] not in domains:
                return False

            old_state = event_data.get("old_state")
            new_state = event_data.get("new_state")
            if old_state is None or new_state is None:
                return True

            return old_state.attributes.get("icon") != new_state.attributes.get("icon")

        @callback
        def _look_again(_: Event) -> None:
            self.inspect_debouncer.async_schedule_call()

        self._event_subs.add(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED, _look_again, event_filter=_icon_changed
            )
        )

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        self.possible_issue_ids.add(self.repair)

        if (icons := await async_get_mdi_icons(self.hass)) is None:
            return

        # In the order they are read, so each kind of setting stays together.
        found = [
            (where, icon)
            for where, icon in self._icons_in_settings()
            if icons.unknown_name(icon) is not None
        ]
        if not found:
            return

        await async_suggest(self.hass, icons, (icon for _, icon in found))

        self.async_create_issue(
            issue_id=self.repair,
            references=[f"{icon} {where}" for where, icon in found],
            translation_placeholders={
                "icons": _lines(icons, found),
                "version": icons.version,
            },
        )

    def _icons_in_settings(self) -> Iterator[tuple[str, Any]]:
        """Yield every icon a setting holds, with where it was set.

        Settings without an icon come along too, as `None`, and are passed
        over with the icons that are not judged.
        """
        yield from self._icons_on_entities()
        yield from self._icons_in_registries()
        yield from self._icons_in_customize()

    def _icons_on_entities(self) -> Iterator[tuple[str, Any]]:
        """Yield the icons set on entities, helpers and zones."""
        for entry in self.entity_registry.entities.values():
            yield f"on the entity `{entry.entity_id}`", entry.icon

        instances = self.hass.data.get(DATA_INSTANCES, {})
        for domain in sorted(_HELPER_DOMAINS | {_ZONE_DOMAIN}):
            if (component := instances.get(domain)) is None:
                continue

            kind = "zone" if domain == _ZONE_DOMAIN else "helper"
            for entity in list(component.entities):
                yield f"on the {kind} `{entity.entity_id}`", entity.icon

    def _icons_in_registries(self) -> Iterator[tuple[str, Any]]:
        """Yield the icons of areas, floors, labels and categories."""
        for area in self.area_registry.areas.values():
            yield f"on the area {area.name}", area.icon

        for floor in fr.async_get(self.hass).floors.values():
            yield f"on the floor {floor.name}", floor.icon

        for label in lr.async_get(self.hass).labels.values():
            yield f"on the label {label.name}", label.icon

        # A name can be taken once per scope, so the scope says which one.
        for scope, categories in cr.async_get(self.hass).categories.items():
            for category in categories.values():
                yield f"on the category {category.name} ({scope})", category.icon

    def _icons_in_customize(self) -> Iterator[tuple[str, Any]]:
        """Yield the icons `customize:` and `customize_domain:` give out.

        Not `customize_glob:`. Home Assistant keeps only the patterns compiled
        from it, which name nothing a person would recognize as theirs.
        """
        if (customize := self.hass.data.get(DATA_CUSTOMIZE)) is None:
            return

        # pylint: disable-next=protected-access
        for entity_id, attributes in (customize._exact or {}).items():  # noqa: SLF001
            yield f"in `customize:` for `{entity_id}`", attributes.get("icon")

        # pylint: disable-next=protected-access
        for domain, attributes in (customize._domain or {}).items():  # noqa: SLF001
            yield f"in `customize_domain:` for `{domain}`", attributes.get("icon")


def _lines(icons: MdiIcons, found: list[tuple[str, str]]) -> str:
    """Return the findings as a list, each with where it was set."""
    return "\n".join(f"- {icons.describe(icon)} {where}" for where, icon in found)
