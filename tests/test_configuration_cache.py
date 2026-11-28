"""Tests for reading a configuration once, however many ask. #2005."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import gc
from importlib import import_module
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED
from homeassistant.core import CoreState
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.setup import async_setup_component

from custom_components import spook
from custom_components.spook import configuration_cache
from custom_components.spook.action_extraction import RememberedNames
from custom_components.spook.configuration_cache import (
    forget_dashboards,
    per_configuration,
    per_dashboard_node,
    read_once,
    reading_for,
)
from custom_components.spook.const import DOMAIN
from custom_components.spook.never_true_templates import never_true_templates
from custom_components.spook.reference_extraction import (
    config_to_judge,
    without_disabled_steps,
)
from custom_components.spook.repairs import SpookRepairManager
from custom_components.spook.template_extraction import (
    extract_template_strings_from_config,
)
from custom_components.spook.trigger_ids import unknown_trigger_ids

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.config_entries import ConfigEntry
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


class _BlueprintAutomation(_Owner):  # pylint: disable=too-few-public-methods
    """An owner made from a blueprint, like an automation using one."""

    referenced_blueprint = "motion_light.yaml"


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


async def test_a_blueprint_automation_keeps_no_more_with_every_round(
    hass: HomeAssistant,
    owned: WeakKeyDictionary[Any, Any],
) -> None:
    """Test looking again at a blueprint automation keeps nothing new with it.

    What its blueprint switches off is left out of a copy of its
    configuration. A new copy every round meant a new set of readings every
    round, all kept with the automation until it reloaded.
    """
    automation = _BlueprintAutomation()
    config = {
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.motion"}],
        "actions": [
            {"action": "light.turn_on", "enabled": "{{ not use_scene }}"},
            {"condition": "template", "value_template": "{{ 'on' }}"},
        ],
    }

    def _kept() -> int:
        return sum(len(readings) for readings in owned[automation].values())

    with reading_for(automation):
        judged = config_to_judge(automation, config)

        # The premise: the same configuration in, the very same copy out.
        assert judged is not config
        assert config_to_judge(automation, config) is judged

        # A reload that changed it hands over a new configuration.
        assert config_to_judge(automation, dict(config)) is not judged

        found = never_true_templates(hass, "automation", judged)
    kept_after_one_round = _kept()

    for _ in range(5):
        with reading_for(automation):
            assert (
                never_true_templates(
                    hass, "automation", config_to_judge(automation, config)
                )
                == found
            )

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


async def test_a_stopped_reader_keeps_nothing_it_reads_after(
    hass: HomeAssistant,
    owned: WeakKeyDictionary[Any, Any],
) -> None:
    """Test a round still going when its repair went leaves nothing behind.

    A round hands the loop back between automations. Its repair can go in
    one of those gaps, and the round then reads on for a reader no one will
    ever ask again, or forget.
    """
    remembered = RememberedNames()
    stop = remembered.async_follow_actions(hass)
    remembered.start_round(set())
    owner = _Owner()
    read: list[dict[str, Any]] = []

    async def _read(config: dict[str, Any], _shadowed: frozenset[str]) -> set[str]:
        read.append(config)
        return {"light.kitchen"}

    with reading_for(owner):
        await remembered.async_named_in({"actions": []}, frozenset(), _read)
    assert remembered in owned[owner]

    stop()
    assert remembered not in owned[owner]

    with reading_for(owner):
        assert await remembered.async_named_in({"actions": []}, frozenset(), _read) == {
            "light.kitchen"
        }

    assert remembered not in owned[owner]
    assert len(read) == 2  # noqa: PLR2004


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


# The repairs that read the automations, scripts and template helpers of the
# house below, and nothing else, so a reload of Spook stays quick.
_REPAIRS_READING_THE_HOUSE = (
    "automation.repairs.unknown_entity_references",
    "script.repairs.unknown_entity_references",
    "template.repairs.unknown_entity_references",
)


class _HouseReadingRepairManager(SpookRepairManager):
    """Repair manager setting up only the repairs that read the house."""

    async def async_setup(self, *, spread_first_inspections: bool = False) -> None:
        """Set up the repairs reading the house, and none of the others."""
        del spread_first_inspections
        for module in _REPAIRS_READING_THE_HOUSE:
            await self._async_setup_repair_module(
                import_module(f"custom_components.spook.ectoplasms.{module}")
            )


async def _async_set_up_the_house(hass: HomeAssistant) -> tuple[Any, Any]:
    """Set up an automation, a script and a template helper, all three named."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "evening",
                "alias": "Evening",
                "triggers": [{"trigger": "event", "event_type": "dusk"}],
                "actions": [
                    {"action": "light.turn_on", "target": {"entity_id": "light.gone"}}
                ],
            }
        },
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "evening": {
                    "sequence": [
                        {
                            "action": "light.turn_on",
                            "target": {"entity_id": "light.gone"},
                        }
                    ]
                }
            }
        },
    )
    MockConfigEntry(
        domain="template",
        title="Gone",
        options={
            "name": "Gone",
            "template_type": "sensor",
            "state": "{{ states('sensor.gone') }}",
        },
    ).add_to_hass(hass)
    await hass.async_block_till_done()

    instances = hass.data[DATA_INSTANCES]
    return (
        instances["automation"].get_entity("automation.evening"),
        instances["script"].get_entity("script.evening"),
    )


async def _async_let_the_repairs_look(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Let the time pass a repair waits before it looks, and the look end."""
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


class _NoServices:
    """Service manager setting up no actions."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def async_setup(self) -> None:
        """Set up no services."""

    def async_on_unload(self) -> None:
        """Unload no services."""


async def _async_forward_no_platforms(
    _hass: HomeAssistant, _entry: ConfigEntry
) -> None:
    """Forward no ectoplasm setup."""


def _set_up_spook_with_only_the_repairs_reading_the_house(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Have Spook set up the repairs reading the house, and nothing else."""
    monkeypatch.setattr(spook, "PLATFORMS", [])
    monkeypatch.setattr(spook, "link_sub_integrations", lambda _hass: set())
    monkeypatch.setattr(spook, "async_forward_setup_entry", _async_forward_no_platforms)
    monkeypatch.setattr(spook, "SpookServiceManager", _NoServices)
    monkeypatch.setattr(spook, "SpookRepairManager", _HouseReadingRepairManager)


@pytest.mark.usefixtures("skip_dependency_setup")
async def test_reloading_spook_keeps_no_more_with_an_automation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
    owned: WeakKeyDictionary[Any, Any],
) -> None:
    """Test a reload of Spook over an unchanged house keeps nothing new.

    The repairs about entity references kept what an automation or script
    names with that automation or script, but under the repair that read it.
    A reload sets up new repairs, and the automations stay. So every reload
    kept another set of readings with every automation and every script, for
    repairs that were long gone, until the automations themselves reloaded.

    The template helper repair made its own copy of every helper's options
    to read, and a new repair made new copies. Every reload of Spook left
    another set of readings of those in the caches, pushing out what was
    still asked for.
    """
    _set_up_spook_with_only_the_repairs_reading_the_house(monkeypatch)
    hass.set_state(CoreState.running)

    # What the template helper repair hands over to read, every time.
    template_repair = import_module(
        "custom_components.spook.ectoplasms.template.repairs.unknown_entity_references"
    )
    names_given_to_templates = template_repair.names_given_to_templates
    helper_options_read: list[Any] = []

    def _names_given_to_templates(config: Any) -> frozenset[str]:
        if "template_type" in config:
            helper_options_read.append(config)
        return names_given_to_templates(config)

    monkeypatch.setattr(
        template_repair, "names_given_to_templates", _names_given_to_templates
    )

    automation, script = await _async_set_up_the_house(hass)
    entry = MockConfigEntry(domain=DOMAIN, title="Your homie", data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _async_let_the_repairs_look(hass, freezer)

    def _kept(owner: Any) -> int:
        return sum(len(readings) for readings in owned[owner].values())

    # The premise: the repairs did read the house, and kept what they read.
    kept_with_the_automation = _kept(automation)
    kept_with_the_script = _kept(script)
    assert kept_with_the_automation
    assert kept_with_the_script
    assert helper_options_read

    for _ in range(3):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await _async_let_the_repairs_look(hass, freezer)

    # Every reload looked again, at the very same automation and script.
    assert entry.state is ConfigEntryState.LOADED
    assert len(helper_options_read) == 4  # noqa: PLR2004
    assert (
        hass.data[DATA_INSTANCES]["automation"].get_entity("automation.evening")
        is automation
    )

    assert _kept(automation) == kept_with_the_automation
    assert _kept(script) == kept_with_the_script

    # And read the same copy of the helper's options every time.
    assert len({id(options) for options in helper_options_read}) == 1

    assert await hass.config_entries.async_unload(entry.entry_id)
