"""Spook - Your homie. Telling an entity that was removed from one not there yet.

A reference to an entity that is not there looks exactly the same whether the
entity was removed or has not arrived yet: a YAML sensor without a unique ID
whose platform is retrying, a state an integration has not written yet, an
entity of an integration still setting up. None of them has a state, and none
of them is in the entity registry. Reporting that is fine. Removing the
reference on the strength of it is not, so a fix that removes one asks here
first. Absence is not proof.

The proof is Home Assistant's own: the entity registry keeps a record of every
entity it deleted. Removing an entity puts it there, and so does removing the
integration that provided it. Disabling an entity does not, and neither does
its integration being unloaded or failing to set up: those stay registered.
An entity that comes back under the same unique ID leaves the record again.

Home Assistant forgets a deleted entity 30 days after nothing owns it any more,
and keeps one whose integration is still there for as long as that is. Older
leftovers lose their button. That is accepted: forgotten is not proof either.

A reference written as an entity registry ID, rather than an entity ID, is
proof on its own once it no longer resolves. Only a registered entity is ever
handed one, and Home Assistant hands the same one back if the entity returns.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .entity_filtering import async_get_deleted_entities

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant

# What Home Assistant hands out as an entity registry ID: a UUID, written as
# 32 lowercase hexadecimal characters. Nothing else in an entity setting is
# ever spelled that way, and anything else that does not resolve is a typo,
# not a leftover of something that was registered.
_REGISTRY_ID_SHAPE = re.compile(r"\A[0-9a-f]{32}\Z")


def is_registry_id_shaped(reference: str) -> bool:
    """Return whether a reference is written as an entity registry ID."""
    return bool(_REGISTRY_ID_SHAPE.match(reference))


@callback
def async_deleted_entry(
    hass: HomeAssistant, reference: str
) -> er.DeletedRegistryEntry | None:
    """Return the entity registry's record of deleting this, if it has one.

    Asked of the registry as it is right now. Spook's own map of deleted
    entities is only told when an entity is deleted or comes back: Home
    Assistant forgetting one after a month raises no event at all, so the
    map can still name one the registry let go of.
    """
    registry = er.async_get(hass)

    if is_registry_id_shaped(reference):
        if registry.entities.get_entry(reference) is not None:
            return None

        return next(
            (
                deleted
                for deleted in registry.deleted_entities.values()
                if deleted.id == reference
            ),
            None,
        )

    # Registered right now, under that entity ID, is no longer deleted. It
    # may even be a different entity than the one that was.
    if registry.async_get(reference) is not None:
        return None

    if (remembered := async_get_deleted_entities(hass).get(reference)) is None:
        return None

    deleted = registry.deleted_entities.get(
        (remembered.domain, remembered.platform, remembered.unique_id)
    )
    if deleted is None or deleted.entity_id != reference:
        return None

    return deleted


@callback
def async_removed_on_purpose(
    hass: HomeAssistant, references: Iterable[str]
) -> set[str]:
    """Return which of these references Home Assistant removed, with proof.

    For an entity ID, that is the entity registry's record of deleting it.
    For an entity registry ID, that it no longer resolves.
    """
    registry = er.async_get(hass)

    return {
        reference
        for reference in references
        if (
            registry.entities.get_entry(reference) is None
            if is_registry_id_shaped(reference)
            else async_deleted_entry(hass, reference) is not None
        )
    }
