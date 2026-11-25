"""Tests for the entity rename journal and the config rewrite helpers."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er

from custom_components.spook.entity_renames import (
    async_get_entity_renames,
    async_track_entity_renames,
    entity_id_in_config,
    replace_entity_id_in_config,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _rename(hass: HomeAssistant, old: str, new: str) -> None:
    """Fire the registry event a rename puts on the bus."""
    hass.bus.async_fire(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "update", "entity_id": new, "old_entity_id": old},
    )


async def test_a_seen_rename_is_journaled(hass: HomeAssistant) -> None:
    """A rename event lands in the journal as old ID to new ID."""
    async_track_entity_renames(hass)
    _rename(hass, "light.old", "light.new")
    await hass.async_block_till_done()

    assert async_get_entity_renames(hass) == {"light.old": "light.new"}


async def test_updates_without_a_rename_are_ignored(hass: HomeAssistant) -> None:
    """A registry update that changed no entity ID adds nothing."""
    async_track_entity_renames(hass)
    hass.bus.async_fire(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "update", "entity_id": "light.same", "changes": {"icon": "mdi:x"}},
    )
    await hass.async_block_till_done()

    assert async_get_entity_renames(hass) == {}


async def test_a_second_rename_chains_the_first(hass: HomeAssistant) -> None:
    """Renaming the new ID again retargets the journaled mapping."""
    async_track_entity_renames(hass)
    _rename(hass, "light.a", "light.b")
    _rename(hass, "light.b", "light.c")
    await hass.async_block_till_done()

    assert async_get_entity_renames(hass) == {
        "light.a": "light.c",
        "light.b": "light.c",
    }


async def test_a_rename_back_drops_the_old_entry(hass: HomeAssistant) -> None:
    """Renaming `a` back keeps only what is now broken: references to `b`."""
    async_track_entity_renames(hass)
    _rename(hass, "light.a", "light.b")
    _rename(hass, "light.b", "light.a")
    await hass.async_block_till_done()

    assert async_get_entity_renames(hass) == {"light.b": "light.a"}


async def test_an_entity_taking_a_journaled_id_drops_it(hass: HomeAssistant) -> None:
    """A created entity reusing the old ID means the reference works again."""
    async_track_entity_renames(hass)
    _rename(hass, "light.old", "light.new")
    hass.bus.async_fire(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "create", "entity_id": "light.old"},
    )
    await hass.async_block_till_done()

    assert async_get_entity_renames(hass) == {}


async def test_tracking_is_registered_once(hass: HomeAssistant) -> None:
    """Both rename repairs ask for the journal; only one listener goes up."""
    async_track_entity_renames(hass)
    async_track_entity_renames(hass)
    _rename(hass, "light.old", "light.new")
    await hass.async_block_till_done()

    assert async_get_entity_renames(hass) == {"light.old": "light.new"}


def test_entity_id_in_config_matches_standalone_tokens() -> None:
    """Only the entity ID as a whole word counts, not a prefix of another."""
    config = {
        "trigger": {"platform": "state", "entity_id": "light.old"},
        "action": [{"service": "light.turn_on", "entity_id": "light.older"}],
    }
    assert entity_id_in_config(config, "light.old")
    assert not entity_id_in_config(config, "light.new")


def test_entity_id_in_config_finds_jinja_references() -> None:
    """A reference inside a template is found where core sees nothing."""
    config = {
        "condition": {
            "condition": "template",
            "value_template": "{{ states('light.old') == 'on' }}",
        },
    }
    assert entity_id_in_config(config, "light.old")


def test_replace_entity_id_in_config_rewrites_references() -> None:
    """Structural values and Jinja references are rewritten alike."""
    config = {
        "id": "automation-1",
        "trigger": {"platform": "state", "entity_id": ["light.old", "light.other"]},
        "condition": {
            "condition": "template",
            "value_template": "{{ states.light.old.state == 'on' }}",
        },
    }
    new_config, changed = replace_entity_id_in_config(config, "light.old", "light.new")

    assert changed
    assert new_config["trigger"]["entity_id"] == ["light.new", "light.other"]
    assert "light.new" in new_config["condition"]["value_template"]
    assert "light.old" not in str(new_config)


def test_replace_entity_id_in_config_leaves_skip_keys_alone() -> None:
    """Keys that never hold a reference keep their value untouched."""
    config = {
        "id": "light.old",
        "alias": "uses light.old",
        "device_id": "light.old",
        "trigger": {"entity_id": "light.old"},
    }
    new_config, changed = replace_entity_id_in_config(config, "light.old", "light.new")

    assert new_config["id"] == "light.old"
    assert new_config["device_id"] == "light.old"
    assert new_config["alias"] == "uses light.old"
    assert new_config["trigger"]["entity_id"] == "light.new"
    assert changed


def test_replace_entity_id_in_config_without_a_match_changes_nothing() -> None:
    """A config naming another entity reports nothing changed."""
    _, changed = replace_entity_id_in_config(
        {"entity_id": "light.other"}, "light.old", "light.new"
    )
    assert not changed
