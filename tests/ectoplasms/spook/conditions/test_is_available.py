"""Tests for the spook.is_available condition."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.helpers.condition import ConditionConfig
import pytest
import voluptuous as vol

from custom_components.spook.condition import async_get_conditions
from custom_components.spook.ectoplasms.spook.conditions.is_available import (
    SpookCondition,
)

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the condition platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import area_registry as ar, entity_registry as er

SPEAKER = "media_player.bathroom"
PLUG = "switch.desk"


async def _ask(
    hass: HomeAssistant,
    target: dict | None = None,
    **options: object,
) -> bool:
    """Validate, build and ask the condition once."""
    validated = await SpookCondition.async_validate_config(
        hass,
        {"target": target or {"entity_id": SPEAKER}, "options": options},
    )
    condition = SpookCondition(
        hass,
        ConditionConfig(target=validated["target"], options=validated["options"]),
    )
    await condition.async_setup()
    return bool(condition.async_check())


async def test_the_condition_is_discovered(hass: HomeAssistant) -> None:
    """The condition turns up in Spook's discovery, under a plain key."""
    conditions = await async_get_conditions(hass)

    assert conditions["is_available"] is SpookCondition


@pytest.mark.parametrize("target", [None, {}, {"entity_id": []}])
async def test_a_target_is_required(hass: HomeAssistant, target: object) -> None:
    """Without an entity, there is nothing to be available."""
    config = {} if target is None else {"target": target}
    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(hass, config)


async def test_a_behavior_that_makes_no_sense_is_refused(hass: HomeAssistant) -> None:
    """Any or all, nothing else."""
    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(
            hass, {"target": {"entity_id": SPEAKER}, "options": {"behavior": "most"}}
        )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("playing", True),
        (STATE_OFF, True),
        (STATE_UNAVAILABLE, False),
        (STATE_UNKNOWN, False),
    ],
)
async def test_it_passes_for_anything_but_unavailable_or_unknown(
    hass: HomeAssistant, state: str, *, expected: bool
) -> None:
    """Off is still there to talk to; unavailable and unknown are not. #1831."""
    hass.states.async_set(SPEAKER, state)

    assert await _ask(hass) is expected


async def test_an_entity_that_is_not_there_at_all_is_not_available(
    hass: HomeAssistant,
) -> None:
    """Named outright and missing altogether is as unavailable as it gets."""
    assert await _ask(hass) is False


@pytest.mark.parametrize(("behavior", "expected"), [("any", True), ("all", False)])
async def test_any_or_all(
    hass: HomeAssistant, behavior: str, *, expected: bool
) -> None:
    """One speaker that is there is enough for any, not for all."""
    hass.states.async_set(SPEAKER, "idle")
    hass.states.async_set(PLUG, STATE_UNAVAILABLE)

    target = {"entity_id": [SPEAKER, PLUG]}
    assert await _ask(hass, target, behavior=behavior) is expected


async def test_a_disabled_entity_in_an_area_does_not_count(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """An entity that only comes along with the area, and has no state, is left out.

    A disabled entity has no state. Counted as unavailable, it would keep
    a whole room from ever being all there.
    """
    area = area_registry.async_create("Bathroom")
    for unique_id, entity_id in (("speaker", SPEAKER), ("old", "media_player.old")):
        entity_registry.async_get_or_create(
            "media_player",
            "test",
            unique_id,
            suggested_object_id=entity_id.split(".", 1)[1],
        )
        entity_registry.async_update_entity(entity_id, area_id=area.id)
    hass.states.async_set(SPEAKER, "idle")

    assert await _ask(hass, {"area_id": area.id}, behavior="all") is True
