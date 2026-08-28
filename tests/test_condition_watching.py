"""Tests for watching a condition turn true."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook.condition_watching import (
    BACKSTOP,
    CONTEXT_DEPENDENT,
    _announces_every_turn,
    _condition_types,
    _threshold_entities,
    async_condition_watcher,
    async_validate_condition,
)
import custom_components.spook

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

GATE = {"condition": "state", "entity_id": "input_boolean.gate", "state": "on"}
GATE_TEMPLATE = {
    "condition": "template",
    "value_template": "{{ is_state('input_boolean.gate', 'on') }}",
}

TWICE = 2
FIVE = 5.0


async def _watching(
    hass: HomeAssistant,
    config: ConfigType,
) -> tuple[object, list[Context | None]]:
    """Start watching a condition and record the context of every turn."""
    turns: list[Context | None] = []
    watcher = await async_condition_watcher(
        hass,
        await async_validate_condition(hass, config),
        lambda event: turns.append(event.context if event else None),
    )
    watcher.async_start()
    return watcher, turns


async def test_it_reports_the_turn_and_nothing_else(hass: HomeAssistant) -> None:
    """False to true is the event. True to false is not, and neither is staying."""
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    watcher, turns = await _watching(hass, GATE)
    assert watcher.met is False
    assert not turns

    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert watcher.met is True
    assert len(turns) == 1

    # Still true, written again: not a turn.
    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert len(turns) == 1

    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()
    assert watcher.met is False
    assert len(turns) == 1, "reported going false as a turn"

    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert len(turns) == TWICE

    watcher.async_stop()


async def test_a_condition_already_true_is_not_a_turn(hass: HomeAssistant) -> None:
    """Starting to watch something that is already true changes nothing.

    Callers that care about the current value ask for it, which is what keeps
    the trigger from firing on every reload.
    """
    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()

    watcher, turns = await _watching(hass, GATE)

    assert watcher.met is True
    assert not turns, "reported a turn for something that was already true"

    watcher.async_stop()


async def test_a_template_condition_is_found_by_the_backstop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A template condition names no entities that can be read off the config.

    So nothing announces it, and the timer is the only thing that finds it.
    This is why there is a timer at all.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    watcher, turns = await _watching(hass, GATE_TEMPLATE)

    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert not turns, "expected the template to go unnoticed until the backstop"

    freezer.tick(BACKSTOP + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(turns) == 1, "the backstop never asked again"

    watcher.async_stop()


async def test_the_backstop_runs_even_with_entities_to_watch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Half a condition can announce itself while the other half cannot.

    An `and` of a state and a template hands over the state's entity, so it
    would be easy to conclude there is nothing left to poll for. The template
    half still needs asking.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    hass.states.async_set("input_boolean.gate", "on")
    hass.states.async_set("sensor.temp", "10")
    await hass.async_block_till_done()

    watcher, turns = await _watching(
        hass,
        {
            "condition": "and",
            "conditions": [
                GATE,
                {
                    "condition": "template",
                    "value_template": "{{ states('sensor.temp') | int > 20 }}",
                },
            ],
        },
    )
    assert watcher.met is False

    # Only the template half changes, so only the backstop can find it.
    hass.states.async_set("sensor.temp", "25")
    await hass.async_block_till_done()

    freezer.tick(BACKSTOP + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(turns) == 1, "stopped polling because there were entities to watch"

    watcher.async_stop()


async def test_a_condition_that_cannot_answer_counts_as_false(
    hass: HomeAssistant,
) -> None:
    """A missing entity makes a state condition raise, which is not true.

    Worth holding: the alternative is the watcher falling over on something
    Home Assistant considers an ordinary state of affairs.
    """
    watcher, turns = await _watching(
        hass,
        {
            "condition": "state",
            "entity_id": "input_boolean.never_existed",
            "state": "on",
        },
    )

    assert watcher.met is False
    assert not turns

    watcher.async_stop()


async def test_a_condition_written_the_short_way_is_accepted(
    hass: HomeAssistant,
) -> None:
    """People write a single entity, not a list, and a template as a string.

    Validation turns both into what a checker can use. Without it the checker
    raises on every single check instead of answering.
    """
    validated = await async_validate_condition(hass, GATE)
    assert validated["entity_id"] == ["input_boolean.gate"]

    validated = await async_validate_condition(hass, GATE_TEMPLATE)
    assert not isinstance(validated["value_template"], str)


async def test_a_malformed_condition_is_refused(hass: HomeAssistant) -> None:
    """The wrong shape is caught by the schema."""
    with pytest.raises(vol.Invalid):
        await async_validate_condition(hass, {"no": "condition here"})


async def test_a_condition_that_does_not_exist_is_refused(
    hass: HomeAssistant,
) -> None:
    """An unknown condition type is Home Assistant's own refusal, not the schema's.

    Worth pinning the type, because it decides what a caller has to catch:
    this one arrives as a `HomeAssistantError` rather than a `vol.Invalid`.
    """
    with pytest.raises(HomeAssistantError, match="Invalid condition"):
        await async_validate_condition(hass, {"condition": "not_a_condition"})


async def test_a_context_dependent_condition_is_refused(hass: HomeAssistant) -> None:
    """`trigger` asks which trigger fired, and here nothing fired.

    Measured: asked without variables it answers False rather than raising, so
    accepting it would be a wait that never ends and a trigger that never
    fires, with nothing in the log about it.
    """
    with pytest.raises(vol.Invalid, match="no run here"):
        await async_validate_condition(hass, {"condition": "trigger", "id": "abc"})


def test_the_walk_only_descends_through_and_or_not() -> None:
    """Only `and`, `or` and `not` hold conditions. The rest is payload.

    Walked straight rather than through `async_validate_condition`, because no
    condition that exists today carries a nested mapping this could trip over.
    Which is the point: the walk mirrors how Home Assistant reads a condition
    tree, so a payload that happens to hold a `condition` key stays payload if
    one ever does.
    """
    types = set(
        _condition_types(
            {
                "condition": "and",
                "conditions": [
                    GATE,
                    {
                        "condition": "made.up",
                        "options": {"payload": {"condition": "trigger"}},
                    },
                ],
            }
        )
    )

    assert types == {"and", "state", "made.up"}


async def test_a_context_dependent_condition_is_found_when_nested(
    hass: HomeAssistant,
) -> None:
    """Half an `and` is enough to make the whole thing never true."""
    with pytest.raises(vol.Invalid, match="trigger"):
        await async_validate_condition(
            hass,
            {
                "condition": "and",
                "conditions": [GATE, {"condition": "trigger", "id": "abc"}],
            },
        )


def _spook_condition_classes() -> list[type]:
    """Return every condition class Spook ships."""
    conditions = (
        Path(custom_components.spook.__file__).parent / "ectoplasms/spook/conditions"
    )

    return [
        import_module(
            f"custom_components.spook.ectoplasms.spook.conditions.{module_path.stem}"
        ).SpookCondition
        for module_path in sorted(conditions.glob("[a-z]*.py"))
    ]


def test_every_spook_condition_says_whether_it_needs_a_run() -> None:
    """No default, so a new condition has to make up its mind.

    Inheriting a default would mean the answer for a condition nobody thought
    about is whatever the base happens to say, which is how a list goes stale
    quietly. Declaring it on the class is the whole point.
    """
    for condition_class in _spook_condition_classes():
        assert "needs_run_context" in vars(condition_class), (
            f"spook.{condition_class.condition} does not declare "
            "needs_run_context. Say whether it asks about the run it is in: "
            "reading `variables` for the trigger, the context or `this` means "
            "it does, and it cannot then be watched."
        )


def test_the_refusal_list_matches_what_the_conditions_declare() -> None:
    """Keeps `CONTEXT_DEPENDENT` honest as Spook grows more conditions.

    The list is written out by hand so the validator needs no registry, and
    this is what stops it drifting from the classes it is meant to describe.
    """
    declared = {
        f"spook.{condition_class.condition}"
        for condition_class in _spook_condition_classes()
        if condition_class.needs_run_context
    }

    # Home Assistant's own `trigger` condition is the one Spook does not own.
    assert declared | {"trigger"} == CONTEXT_DEPENDENT


async def test_a_template_reaching_into_the_run_is_refused(
    hass: HomeAssistant,
) -> None:
    """`trigger` inside a template is the same problem in a disguise.

    Measured: checked without variables it raises, the watcher reads that as
    false, and the whole thing sits there. So it is refused up front instead.
    """
    with pytest.raises(vol.Invalid, match="reaches for trigger"):
        await async_validate_condition(
            hass,
            {"condition": "template", "value_template": "{{ trigger.id == 'abc' }}"},
        )


async def test_a_template_that_only_mentions_the_word_is_fine(
    hass: HomeAssistant,
) -> None:
    """Which is why Jinja is asked rather than the text searched.

    `sensor.trigger_count` has `trigger` in the name, and the template reaches
    for `states`, not for anything a run provides.
    """
    config = await async_validate_condition(
        hass,
        {
            "condition": "template",
            "value_template": "{{ states('sensor.trigger_count') | int(0) > 3 }}",
        },
    )

    assert config["condition"] == "template"


async def test_the_other_run_scoped_names_are_refused_too(
    hass: HomeAssistant,
) -> None:
    """A run hands out `this`, `repeat` and `wait` as well."""
    for name in ("this", "repeat", "wait"):
        with pytest.raises(vol.Invalid, match=f"reaches for {name}"):
            await async_validate_condition(
                hass,
                {
                    "condition": "template",
                    "value_template": f"{{{{ {name}.whatever is not none }}}}",
                },
            )


async def test_a_run_scoped_name_is_found_behind_an_assignment(
    hass: HomeAssistant,
) -> None:
    """Jinja knows what the template reaches for, not just what it prints."""
    with pytest.raises(vol.Invalid, match="reaches for trigger"):
        await async_validate_condition(
            hass,
            {
                "condition": "template",
                "value_template": "{% set fired = trigger %}{{ fired is not none }}",
            },
        )


async def test_the_turn_carries_the_change_that_caused_it(
    hass: HomeAssistant,
) -> None:
    """Which is how attribution survives all the way up to the automation.

    Reported here rather than only at the trigger, because this is the layer
    that either has the state change or does not.
    """
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    watcher, turns = await _watching(hass, GATE)

    hass.states.async_set(
        "input_boolean.gate", "on", context=Context(user_id="ghost-hunter")
    )
    await hass.async_block_till_done()
    watcher.async_stop()

    assert [turn.user_id for turn in turns if turn] == ["ghost-hunter"]


async def test_the_backstop_has_nothing_to_carry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Nobody makes the clock move, so there is nobody to name."""
    watcher, turns = await _watching(hass, GATE_TEMPLATE)

    hass.states.async_set("input_boolean.gate", "on")
    freezer.tick(BACKSTOP)
    async_fire_time_changed(hass, dt_util.utcnow() + BACKSTOP)
    await hass.async_block_till_done()
    watcher.async_stop()

    assert turns == [None]


async def test_a_sequence_of_one_is_that_one(hass: HomeAssistant) -> None:
    """What the `condition` selector hands over, even for a single condition.

    `cv.CONDITIONS_SCHEMA` normalises to a list, so anything built in the user
    interface arrives as one. Measured: a bare mapping put through the
    selector comes back as a list of one.
    """
    config = await async_validate_condition(hass, [GATE])

    assert config["condition"] == "state"


async def test_a_sequence_of_several_means_all_of_them(hass: HomeAssistant) -> None:
    """A condition sequence is an implicit `and`, as it is everywhere else."""
    config = await async_validate_condition(hass, [GATE, GATE_TEMPLATE])

    assert config["condition"] == "and"
    assert len(config["conditions"]) == TWICE


async def test_an_empty_sequence_is_refused(hass: HomeAssistant) -> None:
    """Nothing to watch is not the same as nothing to say about it."""
    with pytest.raises(vol.Invalid, match="empty"):
        await async_validate_condition(hass, [])


async def test_the_selector_output_is_what_gets_validated(
    hass: HomeAssistant,
) -> None:
    """Put through the real selector, not a hand-made list.

    Which is the point of this one: the shape has to come from Home Assistant
    rather than from an assumption about what the interface sends.
    """
    through_selector = selector.ConditionSelector()(GATE)

    assert isinstance(through_selector, list)
    config = await async_validate_condition(hass, through_selector)
    assert config["condition"] == "state"


async def test_a_turn_it_cannot_be_sure_of_names_nobody(
    hass: HomeAssistant,
) -> None:
    """The case that made attribution wrong: a hidden half turning first.

    Half of this `and` is a template, so nothing announces its turns. The
    template becomes true unnoticed, and the next unrelated update to the
    watched entity is what discovers it. Blaming that update, and whoever
    caused it, would be wrong.
    """
    hass.states.async_set("input_boolean.gate", "on")
    hass.states.async_set("sensor.temp", "10")
    await hass.async_block_till_done()

    watcher, turns = await _watching(
        hass,
        {
            "condition": "and",
            "conditions": [
                GATE,
                {
                    "condition": "template",
                    "value_template": "{{ states('sensor.temp') | int(0) > 20 }}",
                },
            ],
        },
    )
    assert not turns

    # Nothing watches this, so the turn happens without anyone noticing.
    hass.states.async_set("sensor.temp", "25")
    await hass.async_block_till_done()
    assert not turns

    # An unrelated update to the watched entity is what discovers it.
    hass.states.async_set(
        "input_boolean.gate",
        "on",
        {"unrelated": 1},
        context=Context(user_id="innocent-bystander"),
    )
    await hass.async_block_till_done()
    watcher.async_stop()

    assert turns == [None], "blamed a change that merely happened to notice"


def test_which_conditions_announce_their_own_turns() -> None:
    """The rule attribution hangs on, leaf by leaf.

    Measured what `async_extract_entities` really returns for each of these,
    rather than assumed: a `for` turns true with nothing moving and a
    `value_template` reaches for entities that are not extracted. A
    `numeric_state` threshold naming an entity is not extracted either, but
    that one is watched anyway, so it counts.
    """
    sure = [
        {"condition": "state", "entity_id": "a.b", "state": "on"},
        {"condition": "numeric_state", "entity_id": "s.t", "above": 5},
        {"condition": "zone", "entity_id": "device_tracker.me", "zone": "zone.home"},
        {"condition": "numeric_state", "entity_id": "s.t", "above": "input_number.max"},
        {
            "condition": "and",
            "conditions": [
                {"condition": "state", "entity_id": "a.b", "state": "on"},
                {"condition": "numeric_state", "entity_id": "s.t", "above": 5},
            ],
        },
    ]
    unsure = [
        {
            "condition": "state",
            "entity_id": "a.b",
            "state": "on",
            "for": {"minutes": 5},
        },
        {
            "condition": "numeric_state",
            "entity_id": "s.t",
            "value_template": "{{ 1 }}",
            "above": 5,
        },
        {"condition": "template", "value_template": "{{ true }}"},
        {"condition": "time", "after": "22:00:00"},
        {"condition": "sun", "after": "sunset"},
        {
            "condition": "or",
            "conditions": [
                {"condition": "state", "entity_id": "a.b", "state": "on"},
                {"condition": "template", "value_template": "{{ true }}"},
            ],
        },
    ]

    for config in sure:
        assert _announces_every_turn(config), config

    for config in unsure:
        assert not _announces_every_turn(config), config


async def test_a_threshold_moving_is_noticed_at_once(hass: HomeAssistant) -> None:
    """A condition can turn because the line moved, not the measurement.

    Home Assistant does not extract the entity behind a `numeric_state`
    threshold, so nothing would watch it and the turn would wait for the
    backstop. The clock is not touched here, so anything that arrives came
    from the change itself.
    """
    hass.states.async_set("sensor.temp", "18")
    hass.states.async_set("input_number.max", "20")
    await hass.async_block_till_done()

    watcher, turns = await _watching(
        hass,
        {
            "condition": "numeric_state",
            "entity_id": "sensor.temp",
            "above": "input_number.max",
        },
    )
    assert not turns

    hass.states.async_set(
        "input_number.max", "10", context=Context(user_id="line-mover")
    )
    await hass.async_block_till_done()
    watcher.async_stop()

    assert [turn.user_id for turn in turns if turn] == ["line-mover"], (
        "the threshold entity was not watched"
    )


async def test_a_nested_threshold_is_watched_too(hass: HomeAssistant) -> None:
    """Which is where a threshold usually sits: inside an `and`."""
    hass.states.async_set("input_boolean.gate", "on")
    hass.states.async_set("sensor.temp", "18")
    hass.states.async_set("input_number.max", "20")
    await hass.async_block_till_done()

    watcher, turns = await _watching(
        hass,
        {
            "condition": "and",
            "conditions": [
                GATE,
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temp",
                    "above": "input_number.max",
                },
            ],
        },
    )
    assert not turns

    hass.states.async_set("input_number.max", "10")
    await hass.async_block_till_done()
    watcher.async_stop()

    assert len(turns) == 1, "a nested threshold entity was not watched"


async def test_a_number_is_not_mistaken_for_an_entity(hass: HomeAssistant) -> None:
    """Which is why a plain string threshold is safe to treat as an entity.

    Validation coerces a numeric threshold to a float, whichever way it was
    written, so nothing that survives it and is still a string can be a
    number. Measured, because the collector relies on it.
    """
    validated = await async_validate_condition(
        hass,
        {"condition": "numeric_state", "entity_id": "sensor.temp", "above": "5"},
    )

    assert validated["above"] == FIVE
    assert not set(_threshold_entities(validated))

    with pytest.raises(vol.Invalid):
        await async_validate_condition(
            hass,
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temp",
                "above": "not a number and not an entity",
            },
        )
