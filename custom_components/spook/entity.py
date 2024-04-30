"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.entity import Entity, EntityDescription


@dataclass(frozen=True, kw_only=True)
class SpookEntityDescription(EntityDescription):
    """Defines an base Spook entity description."""

    entity_id: str | None = None


class SpookEntity(Entity):
    """Defines an base Spook entity."""

    entity_description: SpookEntityDescription

    _attr_has_entity_name = True

    def __init__(self, description: SpookEntityDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        if description.entity_id:
            self.entity_id = description.entity_id
