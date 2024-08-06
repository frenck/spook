"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lovelace import DOMAIN
from homeassistant.components.lovelace.const import ConfigNotFound
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_LOVELACE_UPDATED,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_entity_ids, async_get_all_entity_ids

if TYPE_CHECKING:
    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )


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
    automatically_clean_up_issues = True

    _dashboards: dict[str, LovelaceStorage | LovelaceYAML]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._dashboards = self.hass.data["lovelace"]["dashboards"]
        await super().async_activate()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass, include_all_none=True)

        # Loop over all dashboards and check if there are unknown entities
        # referenced in the dashboards.
        for dashboard in self._dashboards.values():
            url_path = dashboard.url_path or "lovelace"
            self.possible_issue_ids.add(url_path)
            try:
                config = await dashboard.async_load(force=False)
            except ConfigNotFound:
                LOGGER.debug("Config for dashboard %s not found, skipping", url_path)
                continue

            if unknown_entities := async_filter_known_entity_ids(
                self.hass,
                entity_ids=self.__async_extract_entities(config),
                known_entity_ids=known_entity_ids,
            ):
                title = "Overview"
                if dashboard.config:
                    title = dashboard.config.get("title", url_path)
                self.async_create_issue(
                    issue_id=url_path,
                    translation_placeholders={
                        "entities": "\n".join(
                            f"- `{entity_id}`" for entity_id in unknown_entities
                        ),
                        "dashboard": title,
                        "edit": f"/{url_path}/0?edit=1",
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown entities in dashboard %s "
                        "and created an issue for it; Entities: %s"
                    ),
                    title,
                    ", ".join(unknown_entities),
                )

    @callback
    def __async_extract_entities(self, config: dict[str, Any]) -> set[str]:
        """Extract entities from a dashboard config."""
        entities = set()
        if isinstance(config, dict) and (views := config.get("views")):
            for view in views:
                entities.update(self.__async_extract_entities_from_view(view))
        return entities

    @callback
    def __async_extract_entities_from_view(self, config: dict[Any]) -> set[str]:
        """Extract entities from a view config."""
        entities = set()
        if badges := config.get("badges"):
            for badge in badges:
                entities.update(self.__async_extract_entities_from_badge(badge))
        if cards := config.get("cards"):
            for card in cards:
                entities.update(self.__async_extract_entities_from_card(card))
        if sections := config.get("sections"):
            for section in sections:
                entities.update(self.__async_extract_entities_from_section(section))
        return entities

    @callback
    def __async_extract_entities_from_section(self, config: dict[Any]) -> set[str]:
        """Extract entities from a section config."""
        entities = set()
        if cards := config.get("cards"):
            for card in cards:
                entities.update(self.__async_extract_entities_from_card(card))
        return entities

    @callback
    def __async_extract_common(self, config: dict[str, Any] | str) -> set[str]:
        """Extract entities from common dashboard config."""
        entities: set[str] = set()

        if not isinstance(config, dict):
            return entities

        for key in ("camera_image", "entity", "entities", "entity_id"):
            if entity := config.get(key):
                if isinstance(entity, str):
                    entities.add(entity)
                if isinstance(entity, list):
                    for item in entity:
                        if isinstance(item, str):
                            entities.add(item)
                        elif (
                            isinstance(item, dict)
                            and "entity" in item
                            and isinstance(item["entity"], str)
                        ):
                            entities.add(item["entity"])
                if (
                    isinstance(entity, dict)
                    and "entity" in entity
                    and isinstance(entity["entity"], str)
                ):
                    entities.add(entity["entity"])
        return entities

    @callback
    def __async_extract_entities_from_badge(
        self,
        config: dict[str, Any] | str,
    ) -> set[str]:
        """Extract entities from a dashboard badge config."""
        if isinstance(config, str):
            return {config}
        if isinstance(config, dict):
            if (entity_id := config.get("entity")) and isinstance(entity_id, str):
                return {config["entity"]}
            if (entities := config.get("entities")) and isinstance(entities, list):
                extracted = []
                for entity in entities:
                    if isinstance(entity, str):
                        extracted.append(entity)
                    elif (
                        isinstance(entity, dict)
                        and "entity" in entity
                        and isinstance(entity["entity"], str)
                    ):
                        extracted.append(entity["entity"])
                return set(extracted)
        return set()

    @callback
    def __async_extract_entities_from_card(  # noqa: C901
        self,
        config: dict[str, Any],
    ) -> set[str]:
        """Extract entities from a dashboard card config."""
        if not isinstance(config, dict):
            return set()

        entities = self.__async_extract_common(config)
        entities.update(self.__async_extract_entities_from_actions(config))

        if condition := config.get("condition"):
            entities.update(
                self.__async_extract_entities_from_condition(condition),
            )

        if card := config.get("card"):
            entities.update(self.__async_extract_entities_from_card(card))

        if cards := config.get("cards"):
            for card in cards:
                entities.update(self.__async_extract_entities_from_card(card))

        for key in ("header", "footer"):
            if header_footer := config.get(key):
                entities.update(
                    self.__async_extract_entities_from_header_footer(header_footer),
                )

        if elements := config.get("elements"):
            for element in elements:
                entities.update(self.__async_extract_entities_from_element(element))

        # Mushroom
        if chips := config.get("chips"):
            for chip in chips:
                entities.update(self.__async_extract_entities_from_mushroom_chip(chip))

        return entities

    @callback
    def __async_extract_entities_from_actions(self, config: dict[str, Any]) -> set[str]:
        """Extract entities from a dashboard config containing actions."""
        entities = set()
        for key in (
            "tap_action",
            "hold_action",
            "double_tap_action",
            "subtitle_tap_action",
        ):
            if isinstance(config, dict) and (action := config.get(key)):
                entities.update(self.__async_extract_entities_from_action(action))
        return entities

    @callback
    def __async_extract_entities_from_action(self, config: dict[str, Any]) -> set[str]:
        """Extract entities from a dashboard action config."""
        entities = set()
        for key in ("service_data", "target"):
            if (
                isinstance(config, dict)
                and (target := config.get(key))
                and isinstance(target, dict)
                and (entity_id := target.get("entity_id"))
            ):
                if isinstance(entity_id, str):
                    entities.add(entity_id)
                if isinstance(entity_id, list):
                    entities.update(entity_id)
        return entities

    @callback
    def __async_extract_entities_from_condition(
        self,
        config: dict[str, Any],
    ) -> set[str]:
        """Extract entities from a dashboard element config."""
        if "entity" in config and isinstance(config["entity"], str):
            return {config["entity"]}
        return set()

    @callback
    def __async_extract_entities_from_element(self, config: dict[str, Any]) -> set[str]:
        """Extract entities from a dashboard element config."""
        if not isinstance(config, dict):
            return set()

        entities = self.__async_extract_common(config)
        entities.update(self.__async_extract_entities_from_actions(config))
        entities.update(self.__async_extract_entities_from_action(config))

        if conditions := config.get("conditions"):
            for condition in conditions:
                entities.update(self.__async_extract_entities_from_condition(condition))

        if elements := config.get("elements"):
            for element in elements:
                entities.update(self.__async_extract_entities_from_element(element))

        return entities

    @callback
    def __async_extract_entities_from_header_footer(
        self,
        config: dict[str, Any],
    ) -> set[str]:
        """Extract entities from a dashboard haeder footer config."""
        entities = self.__async_extract_common(config)
        entities.update(self.__async_extract_entities_from_actions(config))
        return entities

    @callback
    def __async_extract_entities_from_mushroom_chip(
        self,
        config: dict[str, Any],
    ) -> set[str]:
        """Extract entities from mushroom chips."""
        entities = self.__async_extract_common(config)
        if chip := config.get("chip"):
            entities.update(
                self.__async_extract_entities_from_mushroom_chip(chip),
            )
        if conditions := config.get("conditions"):
            for condition in conditions:
                entities.update(self.__async_extract_entities_from_condition(condition))
        return entities
