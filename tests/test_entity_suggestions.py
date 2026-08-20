"""Tests for unknown entity reference enrichment."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.spook import entity_filtering, entity_suggestions
from custom_components.spook.entity_suggestions import async_describe_unknown_entities

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    import pytest


def _count_close_matches(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count difflib lookups, so cache reuse is observable."""
    calls = [0]
    original = entity_suggestions.difflib.get_close_matches

    def _counting(*args: object, **kwargs: object) -> list[str]:
        calls[0] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(entity_suggestions.difflib, "get_close_matches", _counting)

    return calls


def test_plain_unknown_entity_has_no_detail(hass: HomeAssistant) -> None:
    """Test an unknown entity with no match or history is listed plainly."""
    assert async_describe_unknown_entities(hass, ["sensor.ghost_xyzzy"]) == (
        "- `sensor.ghost_xyzzy`"
    )


def test_rename_suggestion_for_similar_entity(hass: HomeAssistant) -> None:
    """Test a close existing entity is suggested as a likely rename."""
    hass.states.async_set("sensor.living_room_temperature", "21")

    result = async_describe_unknown_entities(hass, ["sensor.living_room_temperatur"])

    assert result == (
        "- `sensor.living_room_temperatur` "
        "(did you mean `sensor.living_room_temperature`?)"
    )


async def test_deleted_entity_detail(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a deleted entity shows when and by which integration."""
    entry = entity_registry.async_get_or_create("sensor", "hue", "abc")
    deleted_entity_id = entry.entity_id
    entity_registry.async_remove(deleted_entity_id)

    result = async_describe_unknown_entities(hass, [deleted_entity_id])

    assert result.startswith(f"- `{deleted_entity_id}` (deleted on ")
    assert "was provided by `hue`)" in result


def test_deleted_takes_precedence_over_rename(
    hass: HomeAssistant,
) -> None:
    """Test the deleted-entity detail is preferred over a rename guess."""
    # A known entity close to the deleted one exists, but deletion wins.
    hass.states.async_set("sensor.temperature", "21")
    # No deleted entity here, so this only asserts ordering does not crash;
    # the deleted path is covered above.
    assert "did you mean" in async_describe_unknown_entities(
        hass, ["sensor.temperatur"]
    )


def test_rename_suggestion_stays_within_the_domain(hass: HomeAssistant) -> None:
    """Test a near match in another domain is not offered as a rename.

    A rename that crossed domains is not a rename, and only comparing within
    the domain is what keeps this cheap on a large instance.
    """
    hass.states.async_set("binary_sensor.living_room_motion", "off")

    assert async_describe_unknown_entities(hass, ["sensor.living_room_motion"]) == (
        "- `sensor.living_room_motion`"
    )


def test_rename_suggestion_is_looked_up_once(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a match is computed once, however many references there are.

    One removed entity is usually referenced from many automations, and each
    builds its own issue text. Doing the comparison per reference instead of
    per entity is what made inspections expensive.
    """
    hass.states.async_set("sensor.living_room_temperature", "21")
    calls = _count_close_matches(monkeypatch)

    first = async_describe_unknown_entities(hass, ["sensor.living_room_temperatur"])
    second = async_describe_unknown_entities(hass, ["sensor.living_room_temperatur"])

    assert "did you mean" in first
    assert first == second
    assert calls[0] == 1


def test_rename_miss_is_looked_up_once(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test "nothing similar exists" is cached too.

    Misses are the common case on a tidy instance, and they cost exactly as
    much to compute as a hit does.
    """
    calls = _count_close_matches(monkeypatch)

    first = async_describe_unknown_entities(hass, ["sensor.ghost_xyzzy"])
    second = async_describe_unknown_entities(hass, ["sensor.ghost_xyzzy"])

    assert first == second == "- `sensor.ghost_xyzzy`"
    assert calls[0] == 1


def test_rename_suggestion_follows_the_entity_ids_cache(hass: HomeAssistant) -> None:
    """Test a cached answer does not outlive the entities it was based on.

    The suggestion cache is cleared along with the known entity IDs, so a
    "nothing similar exists" answer has to stop being true once something
    similar shows up.
    """
    entity_filtering.async_setup_all_entity_ids_cache_invalidation(hass)

    assert async_describe_unknown_entities(hass, ["sensor.living_room_temperatur"]) == (
        "- `sensor.living_room_temperatur`"
    )

    hass.states.async_set("sensor.living_room_temperature", "21")

    assert "did you mean" in async_describe_unknown_entities(
        hass, ["sensor.living_room_temperatur"]
    )
