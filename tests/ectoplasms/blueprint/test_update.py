"""Tests for the update entities Spook puts on imported blueprints."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState
from homeassistant.exceptions import HomeAssistantError
import aiohttp
import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.spook.ectoplasms.blueprint.update import _CHECK_INTERVAL

from .conftest import (
    A_SCRIPT_BLUEPRINT,
    MOTION_LIGHT,
    MOTION_LIGHT_CHANGED,
    MOTION_LIGHT_WITH_NEW_INPUT,
    NO_INPUTS,
    SOURCE,
    async_add_automation,
    async_set_up,
    async_write_blueprint,
    examples_are_on_disk,
    imported_from,
    write_by_hand,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er

_ENTITY = "update.blueprints_spooky_motion_light"
_FETCH = "custom_components.spook.ectoplasms.blueprint.update.fetch_blueprint_from_url"
_BOTH_OF_THEM = 2


def _source_says(raw: str, *, source: str = SOURCE):  # noqa: ANN202
    """Make the importer hand back this blueprint."""
    return patch(_FETCH, return_value=imported_from(raw, source=source))


async def _check(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let a round of checks come round, the way it does on its own.

    Nothing else brings one on. Blueprints raise no events, so the timer is
    the only thing that ever looks.
    """
    freezer.tick(_CHECK_INTERVAL + timedelta(minutes=1))
    async_fire_time_changed(hass)

    # `async_track_time_interval` runs its job as a background task, which a
    # plain `async_block_till_done` walks straight past. Without this the
    # round is still going when the test moves on.
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_a_blueprint_that_came_from_a_url_gets_an_entity(
    hass: HomeAssistant,
) -> None:
    """Which is the whole premise: a source to compare against."""
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    state = hass.states.get(_ENTITY)
    assert state is not None
    assert state.attributes["release_url"] == SOURCE


async def test_a_blueprint_written_by_hand_is_left_out(
    hass: HomeAssistant,
) -> None:
    """No source means nothing to check against, and no button to offer.

    It is also how somebody opts out of one they no longer want followed:
    take the URL back out of the file. The imported one alongside it is there
    to prove the platform came up at all, rather than falling over on the
    blueprint with no URL and leaving nothing behind either way.
    """
    async_write_blueprint(
        hass,
        "automation",
        "mine.yaml",
        MOTION_LIGHT.replace("  source_url: {source}\n", "").replace(
            "Spooky motion light",
            "Spooky handmade thing",
        ),
    )
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    assert hass.states.async_entity_ids("update") == [_ENTITY]


async def test_a_source_that_still_says_the_same_is_not_an_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The old spellings have to survive the round trip.

    The file on disk says `trigger`, the copy Home Assistant loaded says
    `triggers`, because the automation schema rewrites it. Fingerprinting the
    loaded copy would call every blueprint written before that rename out of
    date, for ever.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT):
        await _check(hass, freezer)

    state = hass.states.get(_ENTITY)
    assert state.state == "off"
    assert state.attributes["latest_version"] == state.attributes["installed_version"]


async def test_a_source_that_has_moved_on_is_an_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The point of the exercise."""
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY).state == "on"


async def test_installing_writes_the_new_blueprint(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """And settles back down afterwards."""
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert "to: 'off'" in file.read_text(encoding="utf-8")
    assert hass.states.get(_ENTITY).state == "off"


async def test_an_update_that_would_strand_an_automation_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An input with no default has to come from whoever uses the blueprint.

    A new one that nobody sets stops every automation on it from loading the
    moment the file is written, and the old version is gone by then.
    """
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    await async_add_automation(
        hass,
        "Landing light",
        "motion.yaml",
        {"motion_entity": "binary_sensor.landing", "light_target": {}},
    )
    before = file.read_text(encoding="utf-8")

    with _source_says(MOTION_LIGHT_WITH_NEW_INPUT):
        await _check(hass, freezer)

        with pytest.raises(HomeAssistantError, match="wait_time"):
            await hass.services.async_call(
                "update",
                "install",
                {"entity_id": _ENTITY},
                blocking=True,
            )

    assert file.read_text(encoding="utf-8") == before


async def test_a_new_input_nobody_needs_to_set_goes_through(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A default is what makes the difference, so it has to be read."""
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    await async_add_automation(
        hass,
        "Landing light",
        "motion.yaml",
        {"motion_entity": "binary_sensor.landing", "light_target": {}},
    )

    with _source_says(
        MOTION_LIGHT_WITH_NEW_INPUT.replace(
            "    wait_time:\n      name: Wait time\n",
            "    wait_time:\n      name: Wait time\n      default: 120\n",
        ),
    ):
        await _check(hass, freezer)
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert "wait_time" in file.read_text(encoding="utf-8")


async def test_a_source_leading_to_another_blueprint_is_not_an_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A community topic can hold more than one blueprint.

    The importer takes the first valid block it comes across, and both got the
    same source URL on the way in. Following it can land on the other one
    entirely, and writing that over this would be the wrong blueprint in the
    wrong file.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(A_SCRIPT_BLUEPRINT):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY).state == "off"


@pytest.mark.parametrize(
    "went_wrong",
    [
        TimeoutError(),
        aiohttp.ClientError(),
        vol.Invalid("that is not a blueprint any more"),
        HomeAssistantError("unsupported URL"),
    ],
)
async def test_a_source_that_cannot_be_read_leaves_the_last_answer_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    went_wrong: Exception,
) -> None:
    """A forum down for an afternoon should not take the news with it."""
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
    assert hass.states.get(_ENTITY).state == "on"

    with patch(_FETCH, side_effect=went_wrong):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY).state == "on"


async def test_a_blueprint_that_is_gone_takes_its_entity_with_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Nothing announces a blueprint being deleted, so the round has to look."""
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    assert entity_registry.async_get(_ENTITY) is not None

    file.unlink()

    with _source_says(MOTION_LIGHT):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY) is None
    assert entity_registry.async_get(_ENTITY) is None


async def test_home_assistants_own_examples_are_left_out(
    hass: HomeAssistant,
) -> None:
    """Home Assistant fills a folder of its own with three example blueprints.

    All three carry a source URL pointing at core's dev branch. Following them
    would put an update on every installation there is, for something nobody
    imported, out of a branch nobody is running.
    """
    await async_set_up(hass)

    assert examples_are_on_disk(
        hass,
    ), "Home Assistant laid down no examples, so this proves nothing"
    assert not hass.states.async_entity_ids("update")


async def test_a_reimport_somewhere_else_is_noticed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Home Assistant has a re-import button of its own, on the blueprint page.

    Somebody using that settles the update without Spook having any part in
    it, and reading the fingerprint once at startup would leave this saying
    there is an update for ever.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
    assert hass.states.get(_ENTITY).state == "on"

    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT_CHANGED)
    await hass.services.async_call("automation", "reload", blocking=True)
    await hass.async_block_till_done()

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY).state == "off"


async def test_unloading_stops_a_round_that_is_under_way(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A round is a string of network calls, one blueprint after another.

    Cancelling the timer only stops the next round starting. The one already
    running has to notice for itself, or it goes on talking to the internet
    and writing to entities that are no longer there.
    """
    async_write_blueprint(hass, "automation", "one.yaml", MOTION_LIGHT)
    async_write_blueprint(
        hass,
        "automation",
        "two.yaml",
        MOTION_LIGHT.replace("Spooky motion light", "Spooky hallway light"),
    )
    entry = await async_set_up(hass)
    assert len(hass.states.async_entity_ids("update")) == _BOTH_OF_THEM

    reached: list[str] = []

    async def _fetch_then_pull_the_rug(_hass: HomeAssistant, url: str):  # noqa: ANN202
        reached.append(url)
        await hass.config_entries.async_unload(entry.entry_id)
        return imported_from(MOTION_LIGHT)

    with patch(_FETCH, side_effect=_fetch_then_pull_the_rug):
        await _check(hass, freezer)

    assert len(reached) == 1, "it carried on after being unloaded"


async def test_a_blueprint_nobody_dumped_back_out_still_matches(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Both sides have to go through the same schema, not just the same dump.

    This one has no inputs and no `input:` key to say so, and it was written
    by hand rather than laid down by an import. The schema puts an empty one
    in on the way through. Only doing that to the copy that came off the
    internet would call it different for ever.
    """
    write_by_hand(hass, "automation", "fixed.yaml", NO_INPUTS)
    await async_set_up(hass)

    entity_id = "update.blueprints_spooky_fixed_automation"
    assert hass.states.get(entity_id) is not None

    with _source_says(NO_INPUTS):
        await _check(hass, freezer)

    assert hass.states.get(entity_id).state == "off"


async def test_the_entities_arrive_once_home_assistant_is_up(
    hass: HomeAssistant,
) -> None:
    """Which is how it happens on a real start.

    Spook is set up while Home Assistant is still coming up, and the domains
    that hold the blueprints register themselves along the way. Looking right
    then finds nothing at all.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    hass.set_state(CoreState.not_running)

    await async_set_up(hass)
    assert hass.states.get(_ENTITY) is None

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert hass.states.get(_ENTITY) is not None


async def test_a_blueprint_that_cannot_be_read_says_nothing_new(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Listing a blueprint and reading it are two separate goes at the disk.

    It can be deleted or made unreadable in between. Reading nothing as a
    fingerprint of nothing would leave the entity with no version at all and
    no state to show.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
    assert hass.states.get(_ENTITY).state == "on"

    with (
        patch.object(Path, "read_text", side_effect=OSError),
        _source_says(MOTION_LIGHT_CHANGED),
    ):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY).state == "on"
