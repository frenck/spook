"""Tests for automation unknown device reference repairs."""
# ruff: noqa: SLF001
# pylint: disable=protected-access,too-few-public-methods

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from homeassistant.helpers.entity_component import DATA_INSTANCES
from pytest_homeassistant_custom_component.common import MockConfigEntry
import pytest

from custom_components.spook.ectoplasms.automation.repairs.unknown_device_references import (
    SpookRepair,
)
from tests.device_registry_helpers import simulate_composite_split

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterable
    from typing import Any

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr


class MockAutomationEntity:
    """Mock automation entity."""

    def __init__(
        self,
        *,
        raw_config: dict[str, object],
        referenced_devices: Iterable[str],
    ) -> None:
        """Initialize the mock automation entity."""
        self.raw_config = raw_config
        self.referenced_devices = set(referenced_devices)


async def test_event_trigger_data_device_id_is_not_reported_unknown(
    hass: HomeAssistant,
) -> None:
    """Event trigger ``event_data.device_id`` values are not device references."""
    entity = MockAutomationEntity(
        raw_config={
            "trigger": {
                "trigger": "event",
                "event_type": "hcu_integration_event",
                "event_data": {"device_id": "3014F711A0001F20C98F2F47"},
            },
        },
        referenced_devices={"3014F711A0001F20C98F2F47"},
    )
    repair = SpookRepair(hass)
    repair._known_device_ids = set()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_event_trigger_data_device_id_in_plural_triggers_is_not_reported_unknown(
    hass: HomeAssistant,
) -> None:
    """Plural event triggers can contain device IDs that are not device references."""
    entity = MockAutomationEntity(
        raw_config={
            "triggers": [
                {
                    "trigger": "event",
                    "event_type": "hcu_integration_event",
                    "event_data": {"device_id": "3014F711A0001F20C98F2F47"},
                },
            ],
        },
        referenced_devices={"3014F711A0001F20C98F2F47"},
    )
    repair = SpookRepair(hass)
    repair._known_device_ids = set()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_pre_split_device_id_is_not_reported_unknown(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a device ID from before the Core 2026.8 device split is not unknown.

    A device that belonged to multiple config entries was split into one device
    per entry. Its original ID is gone from the registry, but Home Assistant
    still resolves it to the new devices, so the automation keeps working.
    """
    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    split = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "split-device")},
    )
    simulate_composite_split(device_registry, split, "pre-split-id")

    entity = MockAutomationEntity(
        raw_config={
            "actions": [
                {
                    "action": "light.turn_on",
                    "target": {"device_id": "pre-split-id"},
                },
            ],
        },
        referenced_devices={"pre-split-id"},
    )
    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()


def _named_device(device_id: str) -> MockAutomationEntity:
    """Return an automation that targets one device."""
    return MockAutomationEntity(
        raw_config={
            "actions": [
                {"action": "light.turn_on", "target": {"device_id": device_id}},
            ],
        },
        referenced_devices={device_id},
    )


async def _round(repair: SpookRepair, *entities: MockAutomationEntity) -> None:
    """Have ``repair`` go over ``entities`` the way a round does."""
    repair._collecting_device_ids = set()
    await repair._async_setup_inspection()
    for entity in entities:
        await repair._async_compute_unknown_references(entity)
    repair._referenced_device_ids = repair._collecting_device_ids
    repair._collecting_device_ids = None


async def _inspected(
    hass: HomeAssistant, *entities: MockAutomationEntity
) -> SpookRepair:
    """Return a repair that has done a round over ``entities``."""
    repair = SpookRepair(hass)
    await _round(repair, *entities)
    return repair


async def test_every_device_event_is_worth_a_look_before_a_first_round(
    hass: HomeAssistant,
) -> None:
    """Until a round has collected what is named, nothing can be left out."""
    repair = SpookRepair(hass)

    assert repair._device_registry_event_worth_a_look(
        {"action": "create", "device_id": "a" * 32}
    )
    assert repair._device_registry_event_worth_a_look(
        {"action": "update", "device_id": "a" * 32, "changes": {"name": "Old"}}
    )


async def test_device_coming_or_going_that_nothing_names_is_not_worth_a_look(
    hass: HomeAssistant,
) -> None:
    """A device no automation names cannot make a reference known or unknown."""
    repair = await _inspected(hass, _named_device("a" * 32))

    assert not repair._device_registry_event_worth_a_look(
        {"action": "create", "device_id": "b" * 32}
    )
    assert not repair._device_registry_event_worth_a_look(
        {"action": "remove", "device_id": "b" * 32, "device": {}}
    )


async def test_device_coming_or_going_that_is_named_is_worth_a_look(
    hass: HomeAssistant,
) -> None:
    """A device an automation names turns its reference known or unknown."""
    repair = await _inspected(hass, _named_device("a" * 32))

    assert repair._device_registry_event_worth_a_look(
        {"action": "create", "device_id": "a" * 32}
    )
    assert repair._device_registry_event_worth_a_look(
        {"action": "remove", "device_id": "a" * 32, "device": {}}
    )


async def test_device_update_is_not_worth_a_look(hass: HomeAssistant) -> None:
    """An update never changes the ID of a device, so it changes no finding."""
    repair = await _inspected(hass, _named_device("a" * 32))

    assert not repair._device_registry_event_worth_a_look(
        {"action": "update", "device_id": "a" * 32, "changes": {"name": "Old"}}
    )


async def test_device_update_of_the_id_it_was_split_from_is_worth_a_look(
    hass: HomeAssistant,
) -> None:
    """The ID a device was split from is known through it, so a change counts."""
    repair = await _inspected(hass, _named_device("a" * 32))

    assert repair._device_registry_event_worth_a_look(
        {
            "action": "update",
            "device_id": "b" * 32,
            "changes": {"composite_device_id": None},
        }
    )


async def test_split_device_coming_or_going_is_worth_a_look_for_its_old_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A device split from a named ID makes that ID known, and unknown again."""
    repair = await _inspected(hass, _named_device("pre-split-id"))

    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    split = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "split-device")},
    )
    simulate_composite_split(device_registry, split, "pre-split-id")

    assert repair._device_registry_event_worth_a_look(
        {"action": "create", "device_id": split.id}
    )
    assert repair._device_registry_event_worth_a_look(
        {
            "action": "remove",
            "device_id": split.id,
            "device": {"composite_device_id": "pre-split-id"},
        }
    )


async def test_while_a_round_runs_the_last_one_done_still_counts(
    hass: HomeAssistant,
) -> None:
    """A round still collecting has not seen everything the last one did."""
    repair = await _inspected(hass, _named_device("a" * 32))
    # A new round starts, and has only reached another automation so far.
    repair._collecting_device_ids = set()
    await repair._async_setup_inspection()
    await repair._async_compute_unknown_references(_named_device("c" * 32))

    assert repair._device_registry_event_worth_a_look(
        {"action": "remove", "device_id": "a" * 32, "device": {}}
    )
    assert repair._device_registry_event_worth_a_look(
        {"action": "create", "device_id": "c" * 32}
    )
    assert not repair._device_registry_event_worth_a_look(
        {"action": "create", "device_id": "b" * 32}
    )


async def test_a_round_that_fails_keeps_what_the_last_one_found(
    hass: HomeAssistant,
) -> None:
    """Half a round is no account of what is named."""
    repair = await _inspected(hass, _named_device("a" * 32))
    hass.data[DATA_INSTANCES] = {repair.domain: object()}

    async def _fail(_: SpookRepair) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            "custom_components.spook.repairs."
            "AbstractSpookEntityComponentUnknownReferencesRepair.async_inspect",
            _fail,
        )
        with pytest.raises(RuntimeError):
            await repair.async_inspect()

    assert repair._collecting_device_ids is None
    assert repair._device_registry_event_worth_a_look(
        {"action": "remove", "device_id": "a" * 32, "device": {}}
    )


def _round_over(
    *entities: MockAutomationEntity,
    midway: Callable[[SpookRepair], None],
) -> Callable[[SpookRepair], Coroutine[Any, Any, None]]:
    """Return a stand-in for a round, calling ``midway`` when it yields."""

    async def _inspect(repair: SpookRepair) -> None:
        await repair._async_setup_inspection()
        for index, entity in enumerate(entities):
            if index == 1:
                midway(repair)
            await repair._async_compute_unknown_references(entity)

    return _inspect


async def _inspect_with(
    repair: SpookRepair,
    inspect: Callable[[SpookRepair], Coroutine[Any, Any, None]],
) -> None:
    """Have ``repair`` do a full round, with ``inspect`` going over entities."""
    repair.hass.data[DATA_INSTANCES] = {repair.domain: object()}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            "custom_components.spook.repairs."
            "AbstractSpookEntityComponentUnknownReferencesRepair.async_inspect",
            inspect,
        )
        await repair.async_inspect()


async def test_device_going_before_a_round_gets_to_it_looks_again(
    hass: HomeAssistant,
) -> None:
    """A device removed mid-round is still known to that round, so look again."""
    repair = await _inspected(hass, _named_device("a" * 32))
    repair.inspect_debouncer = MagicMock()
    passed_over: list[bool] = []

    await _inspect_with(
        repair,
        _round_over(
            _named_device("a" * 32),
            _named_device("c" * 32),
            midway=lambda r: passed_over.append(
                r._device_registry_event_worth_a_look(
                    {"action": "remove", "device_id": "c" * 32, "device": {}}
                )
            ),
        ),
    )

    assert passed_over == [False]
    assert repair._referenced_device_ids == {"a" * 32, "c" * 32}
    repair.inspect_debouncer.async_schedule_call.assert_called_once()


async def test_device_nothing_names_passed_over_mid_round_does_not_look_again(
    hass: HomeAssistant,
) -> None:
    """Only a device the round turns out to name is worth the extra round."""
    repair = await _inspected(hass, _named_device("a" * 32))
    repair.inspect_debouncer = MagicMock()

    await _inspect_with(
        repair,
        _round_over(
            _named_device("a" * 32),
            _named_device("c" * 32),
            midway=lambda r: r._device_registry_event_worth_a_look(
                {"action": "create", "device_id": "b" * 32}
            ),
        ),
    )

    assert repair._passed_over_device_ids is None
    repair.inspect_debouncer.async_schedule_call.assert_not_called()


async def test_a_round_that_cannot_run_keeps_what_the_last_one_found(
    hass: HomeAssistant,
) -> None:
    """With automations not loaded, a round names nothing, which means nothing."""
    repair = await _inspected(hass, _named_device("a" * 32))
    hass.data.pop(DATA_INSTANCES, None)

    await repair.async_inspect()

    assert repair._referenced_device_ids == {"a" * 32}
    assert repair._device_registry_event_worth_a_look(
        {"action": "remove", "device_id": "a" * 32, "device": {}}
    )
