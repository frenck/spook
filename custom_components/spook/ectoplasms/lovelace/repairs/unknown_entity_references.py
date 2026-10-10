"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_LOVELACE_UPDATED,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....dashboard_extraction import (
    extract_entities_from_dashboard_node,
    extract_not_entity_ids_from_dashboard_node,
)
from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair
from ..dashboards import async_dashboard_configs

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )
    from homeassistant.core import HomeAssistant


@callback
def _async_miscased_entity_ids(
    hass: HomeAssistant, entity_ids: Iterable[str]
) -> set[str]:
    """Return the entity IDs written with capitals, exactly as written.

    The frontend looks an entity up exactly as the card names it, and every
    entity Home Assistant has is lower case. So `light.Kitchen` is never
    found, not even when `light.kitchen` exists, and the card shows it as
    unavailable. Reported as written, so the repair shows what was typed.

    Only one that is an entity ID once lower cased counts, and it passes the
    same checks as any other; anything else was never meant as one.
    """
    written_as: dict[str, set[str]] = {}
    for entity_id in entity_ids:
        if (lower_cased := entity_id.lower()) != entity_id:
            written_as.setdefault(lower_cased, set()).add(entity_id)

    # Nothing counts as known here: whether the lower case one exists or
    # not, the card names something that does not.
    return {
        entity_id
        for lower_cased in async_filter_known_entity_ids(
            hass, entity_ids=written_as, known_entity_ids=set()
        )
        for entity_id in written_as[lower_cased]
    }


async def _async_describe(
    hass: HomeAssistant, unknown_entities: set[str], not_entity_ids: set[str]
) -> str:
    """Return the issue's list of entities, saying which are no entity ID.

    No guess at what one of those was meant to be. `cover.blind.position` may
    have meant the cover, its position or something else entirely, and a
    wrong suggestion is worse than none.
    """
    lines = [
        await async_describe_unknown_entities(hass, sorted(unknown_entities)),
        *(f"- `{value}` (not an entity ID)" for value in sorted(not_entity_ids)),
    ]
    return "\n".join(line for line in lines if line)


def _first_view_with(
    config: Any, unknown_entities: set[str], not_entity_ids: set[str]
) -> int | str:
    """Return the path of the first view holding something reported.

    Each view is asked with the walk that reported it: the same malformed
    value may sit on a custom card on an earlier view, which only the entity
    walk reads, and that view would be the wrong one to open.
    """
    views = config.get("views") if isinstance(config, dict) else None
    for view_index, view in enumerate(views if isinstance(views, list) else []):
        if not isinstance(view, dict):
            continue

        if unknown_entities & extract_entities_from_dashboard_node(
            view
        ) or not_entity_ids & extract_not_entity_ids_from_dashboard_node(view):
            return view.get("path") or view_index

    # A strategy dashboard has no views stored; its views open from the first.
    return 0


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced entity in dashboards."""

    domain = DOMAIN
    repair = "lovelace_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True
    inspect_on_entity_added_or_removed = True
    automatically_clean_up_issues = True

    _dashboards: dict[str | None, LovelaceStorage | LovelaceYAML]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._dashboards = self.hass.data["lovelace"].dashboards
        await super().async_activate()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass, include_all_none=True)

        # Loop over all dashboards and check if there are unknown entities
        # referenced in the dashboards.
        async for dashboard, url_path, config in async_dashboard_configs(
            self._dashboards
        ):
            self.possible_issue_ids.add(url_path)
            if config is None:
                continue

            extracted_entities = self.__async_extract_entities(config)
            not_entity_ids = extract_not_entity_ids_from_dashboard_node(config)
            unknown_entities = async_filter_known_entity_ids(
                self.hass,
                entity_ids=set(extracted_entities.keys()),
                known_entity_ids=known_entity_ids,
            ) | _async_miscased_entity_ids(self.hass, extracted_entities)
            if unknown_entities or not_entity_ids:
                first_view_path = _first_view_with(
                    config, unknown_entities, not_entity_ids
                )
                title = "Overview"
                if dashboard.config:
                    title = dashboard.config.get("title", url_path)
                self.async_create_issue(
                    issue_id=url_path,
                    references=unknown_entities | not_entity_ids,
                    translation_placeholders={
                        "entities": await _async_describe(
                            self.hass, unknown_entities, not_entity_ids
                        ),
                        "dashboard": title,
                        "edit": f"/{url_path}/{first_view_path}?edit=1",
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown entities in dashboard %s "
                        "and created an issue for it; Entities: %s"
                    ),
                    title,
                    ", ".join(unknown_entities | not_entity_ids),
                )

    @callback
    def __async_extract_entities(self, config: dict[str, Any]) -> dict[str, int | str]:
        """Extract entities from a dashboard config, keyed by their view path."""
        entities: dict[str, int | str] = {}
        if isinstance(config, dict) and (views := config.get("views")):
            for view_index, view in enumerate(views):
                if not isinstance(view, dict):
                    continue
                view_path: int | str = view.get("path") or view_index
                for entity_id in extract_entities_from_dashboard_node(view):
                    entities.setdefault(entity_id, view_path)

        # A dashboard run by a strategy, like the areas dashboard, has no views
        # stored at all: only the strategy and its options. The views it makes
        # are opened from the first one.
        if isinstance(config, dict) and isinstance(
            strategy := config.get("strategy"), dict
        ):
            for entity_id in extract_entities_from_dashboard_node(strategy):
                entities.setdefault(entity_id, 0)

        return entities
