"""Shared helper for tests that need entities their domain loaded itself."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from homeassistant.core import split_entity_id
from homeassistant.helpers.entity_component import DATA_INSTANCES

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class _Component(SimpleNamespace):  # pylint: disable=too-few-public-methods
    """Stand in for an entity component, holding entities by ID only."""

    def get_entity(self, entity_id: str) -> SimpleNamespace | None:
        """Return the entity, like the component does, or None."""
        return self.held.get(entity_id)


def give_entity_objects(
    hass: HomeAssistant, *entity_ids: str, kind: type | None = None
) -> None:
    """Make these entities ones their domain holds, not just states.

    Each is an instance of `kind`, like core's own `LightEntity`, so what it
    is can be looked at; without one it is a plain object, which is no kind
    of entity core knows. Their states are still set with
    `hass.states.async_set`, which is what the recorder records. Only for
    domains no test loads for real.
    """
    instances = hass.data.setdefault(DATA_INSTANCES, {})
    for entity_id in entity_ids:
        domain = split_entity_id(entity_id)[0]
        component = instances.setdefault(domain, _Component(held={}))
        entity = SimpleNamespace() if kind is None else kind()
        entity.entity_id = entity_id
        component.held[entity_id] = entity
