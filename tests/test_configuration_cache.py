"""Tests for reading a configuration once, however many ask. #2005."""

from __future__ import annotations

import asyncio
import gc
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

import pytest

from homeassistant.const import EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED

from custom_components.spook import configuration_cache
from custom_components.spook.action_extraction import RememberedNames
from custom_components.spook.configuration_cache import (
    forget_dashboards,
    per_configuration,
    per_dashboard_node,
    read_once,
    reading_for,
)
from custom_components.spook.reference_extraction import without_disabled_steps
from custom_components.spook.template_extraction import (
    extract_template_strings_from_config,
)
from custom_components.spook.trigger_ids import unknown_trigger_ids

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _counted() -> tuple[Any, list[Any]]:
    """Return a remembered reader, and the configurations it really read."""
    read: list[Any] = []

    @per_configuration
    def _reader(config: Any, extra: Any = None) -> int:
        _ = extra
        read.append(config)
        return len(read)

    return _reader, read


class _Owner:  # pylint: disable=too-few-public-methods
    """Something readings can be kept with, like an automation."""


@pytest.fixture(name="owned", autouse=True)
def owned_fixture(monkeypatch: pytest.MonkeyPatch) -> WeakKeyDictionary[Any, Any]:
    """Return what is kept with owners, without what other tests left there."""
    owned: WeakKeyDictionary[Any, Any] = WeakKeyDictionary()
    monkeypatch.setattr(configuration_cache, "_READINGS", owned)
    return owned


def test_the_same_configuration_is_read_once() -> None:
    """Test asking about one configuration again hands out what was read."""
    reader, read = _counted()
    config = {"actions": []}

    assert reader(config) == 1
    assert reader(config) == 1
    assert read == [config]


def test_an_equal_configuration_is_read_on_its_own() -> None:
    """Test a configuration that only looks the same is read again.

    A reload builds a new configuration, and what it says may have changed in
    a way an equal one would never show: keyed by the configuration itself,
    the new one is always read.
    """
    reader, read = _counted()

    assert reader({"actions": []}) == 1
    assert reader({"actions": []}) == 2  # noqa: PLR2004
    assert len(read) == 2  # noqa: PLR2004


@pytest.mark.parametrize("config", ["{{ x }}", 42, None, ("a", "b")])
def test_what_is_no_configuration_is_always_read(config: Any) -> None:
    """Test only a mapping or a list is remembered."""
    reader, read = _counted()

    reader(config)
    reader(config)

    assert len(read) == 2  # noqa: PLR2004


def test_anything_else_handed_in_is_always_read() -> None:
    """Test a reading that takes more than the configuration is not kept."""
    reader, read = _counted()
    config = {"actions": []}

    reader(config, "more")
    reader(config, extra="more")

    assert len(read) == 2  # noqa: PLR2004


def test_the_oldest_configuration_makes_room(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test only so many configurations are remembered, the oldest goes first."""
    monkeypatch.setattr(configuration_cache, "CACHE_SIZE", 2)
    reader, read = _counted()
    first, second, third = {"a": 1}, {"b": 2}, {"c": 3}

    reader(first)
    reader(second)
    reader(first)  # Asked again, so `second` is now the oldest.
    reader(third)
    reader(first)
    reader(second)

    assert read == [first, second, third, second]


def test_cache_clear_forgets_everything() -> None:
    """Test a cleared reader reads every configuration again."""
    reader, read = _counted()
    config = {"actions": []}

    reader(config)
    reader.cache_clear()
    reader(config)

    assert read == [config, config]


def test_a_configuration_read_once_is_not_remembered() -> None:
    """Test a configuration put together for one reading is not kept.

    No one hands that very object in again, so remembering it would only keep
    it until the cache drops it.
    """
    reader, read = _counted()
    config = {"actions": []}

    with read_once():
        assert reader(config) == 1
        assert reader(config) == 2  # noqa: PLR2004
    assert reader(config) == 3  # noqa: PLR2004
    assert reader(config) == 3  # noqa: PLR2004
    assert read == [config, config, config]


def test_what_is_remembered_is_still_handed_out_when_reading_once() -> None:
    """Test reading once still hands out what was read before."""
    reader, read = _counted()
    config = {"actions": []}

    reader(config)
    with read_once():
        assert reader(config) == 1

    assert read == [config]


async def test_reading_once_stays_with_its_task() -> None:
    """Test another task remembers while one reads once.

    A reading that hands the event loop back lets other tasks run in the
    middle of it, and those keep remembering what they read.
    """
    reader, read = _counted()
    started = asyncio.Event()
    done = asyncio.Event()
    elsewhere = {"actions": []}

    async def _reading_once() -> None:
        with read_once():
            started.set()
            await done.wait()

    async def _remembering() -> None:
        await started.wait()
        reader(elsewhere)
        reader(elsewhere)
        done.set()

    await asyncio.gather(_reading_once(), _remembering())

    assert read == [elsewhere]


def test_what_is_read_for_an_owner_is_read_once() -> None:
    """Test a configuration read for the same owner is read one time."""
    reader, read = _counted()
    owner = _Owner()
    config = {"actions": []}

    with reading_for(owner):
        assert reader(config) == 1
        assert reader(config) == 1

    with reading_for(owner):
        assert reader(config) == 1

    assert read == [config]


def test_what_is_read_for_an_owner_goes_with_it(
    owned: WeakKeyDictionary[Any, Any],
) -> None:
    """Test readings kept with an owner are dropped when the owner is. #2028."""
    reader, _ = _counted()
    owner = _Owner()

    with reading_for(owner):
        reader({"actions": []})

    assert len(owned) == 1

    del owner
    gc.collect()

    assert len(owned) == 0


def test_what_is_read_for_an_owner_takes_no_room_elsewhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test readings kept with an owner push nothing else out."""
    monkeypatch.setattr(configuration_cache, "CACHE_SIZE", 1)
    reader, read = _counted()
    owner = _Owner()
    kept, owned = {"actions": [1]}, {"actions": [2]}

    reader(kept)
    with reading_for(owner):
        reader(owned)
    reader(kept)

    assert read == [kept, owned]


def test_each_owner_has_its_own_readings() -> None:
    """Test one owner going leaves what another read in place."""
    reader, read = _counted()
    stays, goes = _Owner(), _Owner()
    config = {"actions": []}

    with reading_for(stays):
        reader(config)
    with reading_for(goes):
        reader(config)

    del goes
    gc.collect()

    with reading_for(stays):
        reader(config)

    assert read == [config, config]


def test_a_configuration_read_once_is_not_kept_with_an_owner() -> None:
    """Test reading once keeps nothing, with an owner around as well."""
    reader, read = _counted()
    owner = _Owner()
    config = {"actions": []}

    with reading_for(owner), read_once():
        reader(config)
        reader(config)

    assert read == [config, config]


def test_checked_trigger_ids_keep_no_more_with_every_round(
    owned: WeakKeyDictionary[Any, Any],
) -> None:
    """Test looking again at an automation keeps nothing new with it.

    The trigger IDs it checks are read from a copy of its configuration, a
    new one every time. Each of those used to be kept with the automation,
    so every round kept another set until it reloaded.
    """
    owner = _Owner()
    config = {
        "triggers": [{"trigger": "event", "event_type": "ding", "id": "door"}],
        "actions": [
            {"condition": "trigger", "id": "window"},
            {"action": "notify.notify", "data": {"message": "{{ trigger.id }}"}},
        ],
    }

    def _kept() -> int:
        return sum(len(readings) for readings in owned[owner].values())

    with reading_for(owner):
        assert unknown_trigger_ids(config) == {"window"}
    kept_after_one_round = _kept()

    for _ in range(5):
        with reading_for(owner):
            assert unknown_trigger_ids(config) == {"window"}

    assert _kept() == kept_after_one_round


def test_an_owner_that_cannot_be_held_weakly_is_no_owner(
    owned: WeakKeyDictionary[Any, Any],
) -> None:
    """Test readings for such an owner are kept the way they are without one."""
    reader, read = _counted()
    config = {"actions": []}

    with reading_for(SimpleNamespace()):
        reader(config)
    reader(config)

    assert read == [config]
    assert len(owned) == 0


async def test_the_owner_stays_with_its_task(
    owned: WeakKeyDictionary[Any, Any],
) -> None:
    """Test another task taking a turn does not read for this task's owner."""
    reader, _ = _counted()
    owner = _Owner()
    inside = asyncio.Event()
    done = asyncio.Event()

    async def _reads_for_the_owner() -> None:
        with reading_for(owner):
            inside.set()
            await done.wait()

    async def _reads_for_no_one() -> None:
        await inside.wait()
        reader({"actions": []})
        done.set()

    await asyncio.gather(_reads_for_the_owner(), _reads_for_no_one())

    assert len(owned) == 0


def test_disabled_steps_are_left_out_once() -> None:
    """Test the configuration without its disabled steps is worked out once.

    Every repair about automations and scripts starts with it, and they all
    get the very same copy.
    """
    config = {
        "actions": [
            {"action": "light.turn_on", "enabled": False},
            {"action": "light.turn_off"},
        ]
    }

    first = without_disabled_steps(config)

    assert first == {"actions": [{"action": "light.turn_off"}]}
    assert without_disabled_steps(config) is first


def test_templates_of_a_configuration_are_found_once() -> None:
    """Test the templates of one configuration are collected once."""
    config = {"value": "{{ states('light.kitchen') }}", "other": "plain"}

    first = extract_template_strings_from_config(config)

    assert first == ["{{ states('light.kitchen') }}"]
    assert extract_template_strings_from_config(config) is first


def test_dashboard_readings_are_forgotten_when_asked() -> None:
    """Test everything read from dashboards goes once a dashboard changed."""
    read: list[Any] = []

    @per_dashboard_node
    def _reader(node: Any) -> int:
        read.append(node)
        return len(read)

    view = {"cards": []}

    _reader(view)
    _reader(view)
    forget_dashboards()
    _reader(view)

    assert read == [view, view]


def test_forgetting_dashboards_keeps_configurations() -> None:
    """Test forgetting dashboards leaves what was read from automations."""
    reader, read = _counted()
    config = {"actions": []}

    reader(config)
    forget_dashboards()
    reader(config)

    assert read == [config]


async def test_named_in_is_read_once_until_the_actions_change(
    hass: HomeAssistant,
) -> None:
    """Test what a configuration names is read once, and again for new actions."""
    remembered = RememberedNames()
    stop = remembered.async_follow_actions(hass)
    read: list[Any] = []

    async def _read(config: dict[str, Any], shadowed: frozenset[str]) -> set[str]:
        read.append((config, shadowed))
        return {"light.kitchen"}

    config = {"actions": []}
    owner = _Owner()
    remembered.start_round({"light.turn_on"})

    with reading_for(owner):
        assert await remembered.async_named_in(config, frozenset(), _read) == {
            "light.kitchen"
        }
        await remembered.async_named_in(config, frozenset(), _read)
        assert len(read) == 1

        # Other names given to the templates are another reading.
        await remembered.async_named_in(config, frozenset({"states"}), _read)
        assert len(read) == 2  # noqa: PLR2004

        # The same actions next round: still remembered.
        remembered.start_round({"light.turn_on"})
        await remembered.async_named_in(config, frozenset(), _read)
        assert len(read) == 2  # noqa: PLR2004

        # Other actions at the start of a round: read again.
        remembered.start_round({"light.turn_on", "light.toggle"})
        await remembered.async_named_in(config, frozenset(), _read)
        assert len(read) == 3  # noqa: PLR2004

        # An action registered in between: read again.
        hass.bus.async_fire(EVENT_SERVICE_REGISTERED, {"domain": "x", "service": "y"})
        await hass.async_block_till_done()
        await remembered.async_named_in(config, frozenset(), _read)
        assert len(read) == 4  # noqa: PLR2004

        # And one removed.
        hass.bus.async_fire(EVENT_SERVICE_REMOVED, {"domain": "x", "service": "y"})
        await hass.async_block_till_done()
        await remembered.async_named_in(config, frozenset(), _read)
        assert len(read) == 5  # noqa: PLR2004

    stop()


async def test_named_in_goes_with_its_owner(
    owned: WeakKeyDictionary[Any, Any],
) -> None:
    """Test what a configuration names is dropped along with its owner. #2028."""
    remembered = RememberedNames()
    remembered.start_round(set())
    owner = _Owner()

    async def _read(_config: dict[str, Any], _shadowed: frozenset[str]) -> set[str]:
        return {"light.kitchen"}

    with reading_for(owner):
        await remembered.async_named_in({"actions": []}, frozenset(), _read)

    assert len(owned) == 1

    del owner
    gc.collect()

    assert len(owned) == 0


async def test_named_in_is_always_read_without_an_owner() -> None:
    """Test nothing is kept when there is no one to keep it with, like a draft."""
    remembered = RememberedNames()
    remembered.start_round(set())
    read: list[Any] = []

    async def _read(config: dict[str, Any], _shadowed: frozenset[str]) -> set[str]:
        read.append(config)
        return {"light.kitchen"}

    config = {"actions": []}
    await remembered.async_named_in(config, frozenset(), _read)
    await remembered.async_named_in(config, frozenset(), _read)

    assert read == [config, config]


async def test_named_in_hands_out_a_copy(hass: HomeAssistant) -> None:
    """Test a caller changing what it got leaves what is remembered alone."""
    remembered = RememberedNames()
    remembered.start_round(set())

    async def _read(_config: dict[str, Any], _shadowed: frozenset[str]) -> set[str]:
        return {"light.kitchen"}

    config = {"actions": []}
    owner = _Owner()

    with reading_for(owner):
        (await remembered.async_named_in(config, frozenset(), _read)).add("x.y")

        assert await remembered.async_named_in(config, frozenset(), _read) == {
            "light.kitchen"
        }
    _ = hass
