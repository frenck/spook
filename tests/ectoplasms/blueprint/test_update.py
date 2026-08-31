"""Tests for the update entities Spook puts on imported blueprints."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNAVAILABLE
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.core import CoreState, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.blueprint import (
    BLUEPRINT_SCHEMA,
    DOMAIN as BLUEPRINT_DOMAIN,
    Blueprint,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.util import yaml as yaml_util
from annotatedyaml.objects import Input
import aiohttp
import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.blueprint import update as update_module
from custom_components.spook.ectoplasms.blueprint.update import (
    _canonical,
    _in_words,
    _changes,
    _HOW_MANY_LINES,
    _HOW_MANY_TO_NAME,
    _normalize,
    _fingerprint,
    _CHECK_INTERVAL,
    _COPY,
    _KEEP_COPIES,
    _SPREAD,
    BlueprintUpdateEntity,
)

from .conftest import (
    A_SCRIPT_BLUEPRINT,
    A_SCRIPT_BLUEPRINT_CHANGED,
    A_SCRIPT_BLUEPRINT_WITH_A_BAD_STEP,
    A_SCRIPT_BLUEPRINT_WITH_NEW_INPUT,
    ANOTHER_AUTOMATION_BLUEPRINT,
    MOTION_LIGHT,
    MOTION_LIGHT_CHANGED,
    MOTION_LIGHT_CHANGED_AGAIN,
    MOTION_LIGHT_FROM_THE_FUTURE,
    MOTION_LIGHT_WITH_A_BAD_TRIGGER,
    MOTION_LIGHT_WITH_NEW_INPUT,
    NO_INPUTS,
    SOURCE,
    async_add_automation,
    async_write_config,
    async_add_script,
    async_set_up,
    async_write_blueprint,
    examples_are_on_disk,
    imported_from,
    write_by_hand,
)

if TYPE_CHECKING:
    from homeassistant.helpers import device_registry as dr
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from pytest_homeassistant_custom_component.typing import (
        MockHAClientWebSocket,
        WebSocketGenerator,
    )

    from homeassistant.core import Event, HomeAssistant

_ENTITY = "update.spooky_motion_light"
_MOTION_INPUTS = {"motion_entity": "binary_sensor.hall", "light_target": "light.hall"}
_SHOUT_INPUTS = {"notify_target": "mobile_app_phone"}
_FETCH = "custom_components.spook.ectoplasms.blueprint.update.fetch_blueprint_from_url"
_BOTH_OF_THEM = 2
_NOBODY_SAW_IT_COMING = "something nobody saw coming"
_ENOUGH_ROUNDS_TO_JUDGE = 8


def _source_says(raw: str, *, source: str = SOURCE):  # noqa: ANN202
    """Make the importer hand back this blueprint."""
    return patch(_FETCH, return_value=imported_from(raw, source=source))


def _copies_beside(file: Path) -> list[Path]:
    """Return the copies put aside for a blueprint, newest first."""
    return sorted(
        (
            candidate
            for candidate in file.parent.iterdir()
            if (match := _COPY.match(candidate.name)) is not None
            and match["of"] == file.name
        ),
        reverse=True,
    )


async def _check(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let a round of checks come round, the way it does on its own.

    Nothing else brings one on. Blueprints raise no events, so the timer is
    the only thing that ever looks.
    """
    # Past the far end of the window a round picks its next moment from, so
    # this fires whichever moment it happened to choose.
    freezer.tick(_CHECK_INTERVAL + _SPREAD + timedelta(minutes=1))
    async_fire_time_changed(hass)

    # Waiting on background tasks too, so nothing of the round is still going
    # when the test moves on.
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_a_blueprint_that_came_from_a_url_gets_an_entity(
    hass: HomeAssistant,
) -> None:
    """Which is the whole premise: a source to compare against."""
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    state = hass.states.get(_ENTITY)
    assert state is not None
    assert state.attributes["title"] == "Spooky motion light"


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


async def test_an_update_that_strands_an_automation_still_installs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An input with no default has to come from whoever uses the blueprint.

    A new one that nobody sets stops every automation on it from loading. That
    is worth saying loudly and it is not worth refusing over: updating and then
    filling the new setting in is a perfectly ordinary way round, and which way
    round somebody wants is not Spook's to decide.

    What makes it ordinary is that nothing is lost. The automation goes
    unavailable and keeps its configuration and its ID, and its editor reads
    the file rather than the entity, so it opens and takes the new setting like
    any other. This pins that, because the whole argument for going ahead rests
    on it.
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
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert file.read_text(encoding="utf-8") != before
    assert "wait_time" in file.read_text(encoding="utf-8")

    # Stopped, as promised.
    stranded = hass.states.get("automation.landing_light")
    assert stranded is not None
    assert stranded.state == STATE_UNAVAILABLE

    # And still there to be put right: its ID survives, which is what its
    # editor is reached by, and it still holds what somebody configured.
    entity = hass.data[DATA_INSTANCES]["automation"].get_entity(
        "automation.landing_light",
    )
    assert entity.unique_id == "landing_light"
    assert entity.raw_config is not None


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
    both = hass.states.async_entity_ids("update")
    assert len(both) == _BOTH_OF_THEM

    reached: list[str] = []

    async def _fetch_then_pull_the_rug(_hass: HomeAssistant, url: str):  # noqa: ANN202
        reached.append(url)
        await hass.config_entries.async_unload(entry.entry_id)
        return imported_from(MOTION_LIGHT)

    with patch(_FETCH, side_effect=_fetch_then_pull_the_rug):
        await _check(hass, freezer)

    assert len(reached) == 1, "it carried on after being unloaded"

    # And the one that was mid-fetch when the rug went does not put a live
    # state back over the unavailable one that unloading left. Gone through by
    # the names taken before the unload, so an empty list cannot pass this by
    # having nothing to disagree with.
    for entity_id in both:
        left_behind = hass.states.get(entity_id)
        assert left_behind is not None, f"{entity_id} went altogether"
        assert left_behind.state == "unavailable", (
            f"{entity_id} had a state written back after being taken away"
        )


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

    entity_id = "update.spooky_fixed_automation"
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


def _entity(hass: HomeAssistant) -> BlueprintUpdateEntity:
    """Return the update entity itself, for what the dialog cannot reach."""
    return hass.data[DATA_INSTANCES]["update"].get_entity(_ENTITY)


async def _release_notes(
    client: MockHAClientWebSocket,
    entity_id: str = _ENTITY,
) -> str:
    """Ask for the release notes the way the dialog does."""
    await client.send_json_auto_id(
        {"type": "update/release_notes", "entity_id": entity_id},
    )

    result = await client.receive_json()
    assert result["success"], result

    return result["result"]


async def test_the_notes_always_say_where_the_blueprint_came_from(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Even with nothing to install.

    The source is the only thing that can tell somebody what a blueprint
    actually does, so it belongs in front of them rather than a click away.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    assert SOURCE in await _release_notes(client)
    assert (
        UpdateEntityFeature.RELEASE_NOTES
        in hass.states.get(_ENTITY).attributes["supported_features"]
    )


async def test_the_notes_warn_that_an_update_need_not_still_fit(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """There is no changelog, so this is the only warning anybody gets.

    Matter and ZHA put the same sort of thing in front of a firmware update,
    for the same reason: the dialog looks like every other update dialog, and
    this one is not that.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    # Before the clock moves. An access token is good for half an hour, and
    # a round of checks is a day further on than that.
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "alert-type='warning'" in notes
    assert SOURCE in notes


async def test_the_notes_name_the_automations_that_would_be_left_short(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Better than finding out by pressing install and being turned down."""
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    await async_add_automation(
        hass,
        "Landing light",
        "motion.yaml",
        {"motion_entity": "binary_sensor.landing", "light_target": {}},
    )
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_WITH_NEW_INPUT):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    # A warning, not an error: what is listed will stop loading, and putting
    # that right is something somebody can do.
    assert "alert-type='warning'" in notes
    assert "[Landing light](/config/automation/edit/landing_light)" in notes
    assert "Wait time" in notes


async def test_the_notes_do_not_warn_when_there_is_nothing_to_install(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A warning nobody needs is a warning nobody reads."""
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT):
        await _check(hass, freezer)

    assert "ha-alert" not in await _release_notes(client)


async def test_taking_the_source_url_out_of_a_file_is_enough(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """The documented way to be left alone, so it had better work.

    Home Assistant loads a blueprint once and then keeps it, so the copy in
    memory still names a source long after the file stopped doing so. Reading
    the metadata off that copy would leave this entity sitting there checking
    an address the file no longer mentions, until something reloaded.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    assert entity_registry.async_get(_ENTITY) is not None

    write_by_hand(
        hass,
        "automation",
        "motion.yaml",
        MOTION_LIGHT.replace("  source_url: {source}\n", ""),
    )

    with _source_says(MOTION_LIGHT):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY) is None
    assert entity_registry.async_get(_ENTITY) is None


async def test_a_renamed_blueprint_follows_its_new_name(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Same reason: the name comes off the file, not off the loaded copy."""
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    write_by_hand(
        hass,
        "automation",
        "motion.yaml",
        MOTION_LIGHT.replace("Spooky motion light", "Spooky landing light"),
    )

    with _source_says(MOTION_LIGHT):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY).attributes["title"] == "Spooky landing light"


async def test_another_blueprint_at_the_same_address_is_not_this_one(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A forum topic can hold two automation blueprints.

    Both were imported carrying the address of the topic, and the importer
    hands back the first it finds. Matching on the domain alone lets the other
    one through, and installing would write somebody else's blueprint into
    this file.
    """
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    before = file.read_text(encoding="utf-8")
    await async_set_up(hass)

    # Nothing on offer, because what came back is not this blueprint.
    with _source_says(ANOTHER_AUTOMATION_BLUEPRINT):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY).state == "off"

    # And again for the gap in between: an update found honestly, and the
    # topic having moved on by the time somebody presses the button.
    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
    assert hass.states.get(_ENTITY).state == "on"

    with (
        _source_says(ANOTHER_AUTOMATION_BLUEPRINT),
        pytest.raises(HomeAssistantError, match="Spooky doorbell chime"),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY},
            blocking=True,
        )

    assert file.read_text(encoding="utf-8") == before


async def test_a_blueprint_needing_a_newer_home_assistant_is_refused(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A blueprint can say for itself what it needs.

    Writing one that says it needs more than is running breaks every
    automation on it, on a version that was never going to work.
    """
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    before = file.read_text(encoding="utf-8")
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_FROM_THE_FUTURE):
        await _check(hass, freezer)

        assert hass.states.get(_ENTITY).state == "on"
        assert "9999.1.0" in await _release_notes(client)

        with pytest.raises(HomeAssistantError, match=r"9999\.1\.0"):
            await hass.services.async_call(
                "update",
                "install",
                {"entity_id": _ENTITY},
                blocking=True,
            )

    assert file.read_text(encoding="utf-8") == before


async def test_the_notes_say_why_there_is_never_anything_to_install(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """An entity that never has news looks the same as one with nothing to say.

    So when Spook set the answer aside, for a source it could not reach or one
    that leads somewhere else entirely, the dialog says so.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(ANOTHER_AUTOMATION_BLUEPRINT):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "alert-type='info'" in notes
    assert "Spooky doorbell chime" in notes


async def test_a_script_blueprint_gets_one_too(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Scripts keep their blueprint users in a different place from automations.

    Same shape, different integration, and nothing had been through it.
    """
    file = async_write_blueprint(hass, "script", "notify.yaml", A_SCRIPT_BLUEPRINT)
    await async_set_up(hass)

    # With a script actually on it, so the update is tried on that script the
    # way a reload would try it, through the script validator rather than the
    # automation one.
    await async_add_script(
        hass,
        "shout",
        "notify.yaml",
        {"notify_target": "mobile_app_phone"},
    )

    entity_id = "update.spooky_confirmable_notification"
    assert hass.states.get(entity_id) is not None

    with _source_says(A_SCRIPT_BLUEPRINT_CHANGED):
        await _check(hass, freezer)
        assert hass.states.get(entity_id).state == "on"

        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert "Boo!" in file.read_text(encoding="utf-8")
    assert hass.states.get(entity_id).state == "off"
    assert hass.states.get("script.shout") is not None


async def test_a_script_left_short_of_an_input_still_installs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Scripts hold their supplied inputs in their own entities.

    Reading them wrong would let an update through that leaves every script on
    the blueprint unable to load.
    """
    file = async_write_blueprint(hass, "script", "notify.yaml", A_SCRIPT_BLUEPRINT)
    await async_set_up(hass)
    await async_add_script(
        hass,
        "shout",
        "notify.yaml",
        {"notify_target": "mobile_app_phone"},
    )
    before = file.read_text(encoding="utf-8")

    entity_id = "update.spooky_confirmable_notification"
    with _source_says(A_SCRIPT_BLUEPRINT_WITH_NEW_INPUT):
        await _check(hass, freezer)

        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert file.read_text(encoding="utf-8") != before


async def test_a_consumer_that_cannot_be_read_does_not_stop_the_install(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The inputs an automation supplies are reached for by name.

    Home Assistant offers no public way to them: `raw_config` is the automation
    after the blueprint has already been substituted into it. So if that name
    ever changes, or there is simply nothing behind it, Spook stops being able
    to tell whether an update is safe. Not knowing is not a reason to write.
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

    class _AfterARename:  # pylint: disable=too-few-public-methods
        """The automation as it would look had that name changed upstream.

        Still listed as a user of the blueprint, because the public property
        that answers for that would have been renamed along with it, and still
        carrying `raw_config`, which never says which inputs went in.
        """

        entity_id = "automation.landing_light"
        raw_config: ClassVar[dict[str, object]] = {}

    monkeypatch.setattr(
        hass.data[DATA_INSTANCES]["automation"],
        "get_entity",
        lambda _entity_id: _AfterARename(),
    )

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert file.read_text(encoding="utf-8") != before


async def test_nothing_is_looked_at_while_home_assistant_is_still_starting(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Starting up can take longer than the wait before the first round.

    A round landing in the middle of it reads blueprint domains that have not
    finished arriving, and goes out to the internet while the house is still
    getting dressed.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    hass.set_state(CoreState.not_running)
    await async_set_up(hass)

    with patch(_FETCH) as fetch:
        await _check(hass, freezer)
        assert not fetch.called, "it went looking before Home Assistant was up"

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY).state == "on"


async def test_each_round_picks_its_own_moment_for_the_next(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Otherwise every instance that restarted together lines up.

    On the same hour, every day after, which is the stampede the wait before
    the first round exists to avoid, put back a day later.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    seen: list[float] = []
    schedule = update_module.async_call_later

    def _note_the_delay(
        hass: HomeAssistant,
        delay: float,
        action: object,
    ) -> Callable[[], None]:
        """Write down what the scheduler was asked for, then let it get on."""
        seen.append(delay)
        return schedule(hass, delay, action)

    with (
        patch.object(update_module, "async_call_later", _note_the_delay),
        _source_says(MOTION_LIGHT),
    ):
        # Enough rounds that them all landing on the same moment would not be
        # chance.
        for _ in range(_ENOUGH_ROUNDS_TO_JUDGE):
            await _check(hass, freezer)

    assert seen, "no next round was arranged"
    assert all(
        _CHECK_INTERVAL.total_seconds()
        <= delay
        <= (_CHECK_INTERVAL + _SPREAD).total_seconds()
        for delay in seen
    ), seen
    assert len(set(seen)) > 1, f"every round asked for the same moment: {seen}"


async def test_a_source_answering_with_something_else_entirely(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Home Assistant asserts the YAML it parsed is a mapping.

    A source answering with a list, or a bare string, arrives as an
    `AssertionError`, which is not a `HomeAssistantError` and would otherwise
    take the whole round down with it.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
    assert hass.states.get(_ENTITY).state == "on"

    with patch(_FETCH, side_effect=AssertionError):
        await _check(hass, freezer)

    assert hass.states.get(_ENTITY).state == "on"

    # Named as such, rather than swept up by the round's catch-all, so the
    # dialog can say what happened.
    assert (
        "did not answer with a blueprint"
        in await _entity(
            hass,
        ).async_release_notes()
    )


async def test_one_bad_blueprint_does_not_end_the_round(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The round works through them one at a time.

    So the first to fall over would take everything after it with it.
    Everything expected is dealt with inside the entity; this is for whatever
    is not.
    """
    async_write_blueprint(hass, "automation", "one.yaml", MOTION_LIGHT)
    async_write_blueprint(
        hass,
        "automation",
        "two.yaml",
        MOTION_LIGHT.replace("Spooky motion light", "Spooky hallway light"),
    )
    await async_set_up(hass)

    reached: list[str] = []

    async def _first_one_explodes(_hass: HomeAssistant, url: str):  # noqa: ANN202
        reached.append(url)
        if len(reached) == 1:
            raise RuntimeError(_NOBODY_SAW_IT_COMING)
        return imported_from(MOTION_LIGHT)

    with patch(_FETCH, side_effect=_first_one_explodes):
        await _check(hass, freezer)

    assert len(reached) == _BOTH_OF_THEM, "the round stopped at the first one"


async def test_the_notes_say_when_the_news_has_gone_stale(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An update found last week and a source that has stopped answering since.

    Showing the one without the other reads as though the news is current.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
    assert hass.states.get(_ENTITY).state == "on"

    with patch(_FETCH, side_effect=TimeoutError):
        await _check(hass, freezer)

    # Read off the entity rather than through the dialog: two rounds is two
    # days of clock, and a websocket does not survive being left that long.
    notes = await _entity(hass).async_release_notes()
    assert "alert-type='info'" in notes
    assert "Could not reach" in notes
    assert "alert-type='warning'" in notes, "it dropped the update it had found"


async def test_a_check_and_an_install_do_not_tread_on_each_other(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Both fetch before they write, so whichever finished last used to win.

    A check that started first and landed last would put its own answer back
    over the version that had just been installed, leaving this saying an
    update is waiting for something already here.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
    assert hass.states.get(_ENTITY).state == "on"

    started = asyncio.Event()
    let_go = asyncio.Event()
    calls: list[str] = []

    async def _the_first_one_dawdles(_hass: HomeAssistant, _url: str):  # noqa: ANN202
        calls.append(_url)
        if len(calls) == 1:
            started.set()
            await let_go.wait()
            return imported_from(MOTION_LIGHT_CHANGED)

        # By the time anybody asks again, the source has moved on once more.
        return imported_from(MOTION_LIGHT_CHANGED_AGAIN)

    with patch(_FETCH, side_effect=_the_first_one_dawdles):
        checking = hass.async_create_task(_entity(hass).async_check())
        await started.wait()

        # The check is mid-fetch. Install now, and let the check land after.
        installing = hass.async_create_task(
            hass.services.async_call(
                "update",
                "install",
                {"entity_id": _ENTITY},
                blocking=True,
            ),
        )
        await asyncio.sleep(0)

        let_go.set()
        await checking
        await installing

    await hass.async_block_till_done()

    # What was written is what this now has. A check that landed afterwards
    # with an older answer would leave this offering an update backwards.
    assert hass.states.get(_ENTITY).state == "off", "the check undid the install"


async def test_an_update_that_would_not_load_still_installs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A blueprint can be perfectly good and still produce a broken automation.

    The blueprint schema has nothing whatever to say about triggers, actions
    or a script's sequence, and Home Assistant writes the file before it
    reloads anybody. So a blueprint that passes on the way in takes out every
    automation on it, and the working version it replaced is gone.
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

    with _source_says(MOTION_LIGHT_WITH_A_BAD_TRIGGER):
        await _check(hass, freezer)

        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert file.read_text(encoding="utf-8") != before
    assert hass.states.get("automation.landing_light") is not None


async def test_a_script_update_that_would_not_load_still_installs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Scripts go through a validator of their own, so it needs its own go."""
    file = async_write_blueprint(hass, "script", "notify.yaml", A_SCRIPT_BLUEPRINT)
    await async_set_up(hass)
    await async_add_script(
        hass,
        "shout",
        "notify.yaml",
        {"notify_target": "mobile_app_phone"},
    )
    before = file.read_text(encoding="utf-8")

    entity_id = "update.spooky_confirmable_notification"
    with _source_says(A_SCRIPT_BLUEPRINT_WITH_A_BAD_STEP):
        await _check(hass, freezer)

        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert file.read_text(encoding="utf-8") != before
    assert hass.states.get("script.shout") is not None


async def test_the_notes_say_an_update_would_not_load(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Before the button, not after it."""
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    await async_add_automation(
        hass,
        "Landing light",
        "motion.yaml",
        {"motion_entity": "binary_sensor.landing", "light_target": {}},
    )
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_WITH_A_BAD_TRIGGER):
        await _check(hass, freezer)

        notes = await _release_notes(client)

    assert "alert-type='warning'" in notes
    assert "[Landing light](/config/automation/edit/landing_light)" in notes
    assert "would not load" in notes

    # And the heading over that list says nothing about inputs. There are
    # three ways onto it, and blaming the commonest of them sends somebody off
    # setting inputs that were never the trouble.
    heading = notes.partition("<ha-alert alert-type='error'>")[2].partition(
        "</ha-alert>",
    )[0]
    assert "input" not in heading, heading


async def test_installing_clears_what_the_last_look_could_not_do(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An install is a fetch that worked, so the old complaint is stale news.

    A source that went quiet for a round and was back by the time somebody
    pressed the button would otherwise leave the dialog saying it could not be
    reached, until tomorrow.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    with patch(_FETCH, side_effect=TimeoutError):
        await _check(hass, freezer)
    assert "Could not reach" in await _entity(hass).async_release_notes()

    with _source_says(MOTION_LIGHT_CHANGED):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get(_ENTITY).state == "off"
    assert "Could not reach" not in await _entity(hass).async_release_notes()


async def test_where_a_blueprint_came_from_is_not_told_to_everybody(
    hass: HomeAssistant,
) -> None:
    """Home Assistant keeps blueprints to admins.

    Every one of its blueprint commands is admin only, and so is asking an
    update entity for its notes. State attributes are not: anything put there
    is readable by everybody signed in, and a blueprint can be imported from
    an address carrying a token or a username and password.
    """
    async_write_blueprint(
        hass,
        "automation",
        "motion.yaml",
        MOTION_LIGHT,
        source="https://someone:hunter2@example.com/blueprints/motion.yaml",
    )
    await async_set_up(hass)

    assert "hunter2" not in str(hass.states.get(_ENTITY).attributes)

    # Still in front of the people allowed to see it, though.
    assert "hunter2" in await _entity(hass).async_release_notes()


def test_the_fingerprint_ignores_how_the_yaml_was_laid_out() -> None:
    """It used to hash `blueprint.yaml()`, which is a formatting decision.

    `annotatedyaml` picks `CSafeDumper` when libyaml is installed and Python's
    `SafeDumper` when it is not, and the two disagree about unicode escaping,
    folding and line width. On one real blueprint that was 5761 differing
    lines. Hashing their output made the version depend on which one happened
    to be available.

    Written out as two fixed texts rather than by running both dumpers,
    because `CSafeDumper` does not exist in the very environment this is
    about, and the test would then fail there for the wrong reason.
    """
    escaped = (
        "blueprint:\n"
        "  name: Sensor Light\n"
        "  domain: automation\n"
        '  description: "Lights \\U0001F4A1 and a line long enough that a dumper\n'
        '    is free to fold it wherever it likes."\n'
        "triggers: []\n"
    )
    literal = (
        "blueprint:\n"
        "  name: Sensor Light\n"
        "  domain: automation\n"
        "  description: Lights 💡 and a line long enough that a dumper is free to fold\n"
        "    it wherever it likes.\n"
        "triggers: []\n"
    )
    assert escaped != literal, "the two layouts are the same, so this proves nothing"

    one = Blueprint(yaml_util.parse_yaml(escaped), schema=BLUEPRINT_SCHEMA)
    other = Blueprint(yaml_util.parse_yaml(literal), schema=BLUEPRINT_SCHEMA)

    assert (
        one.data["blueprint"]["description"] == other.data["blueprint"]["description"]
    )
    assert _fingerprint(one) == _fingerprint(other)


def test_the_fingerprint_ignores_where_it_came_from() -> None:
    """Home Assistant writes the source URL into the data on the way in.

    So the URL was part of the version, and a trailing slash on it read as a
    new release of the blueprint. Where something was fetched from is not part
    of what it does.
    """
    raw = """
blueprint:
  name: Sensor Light
  domain: automation
triggers: []
"""
    url = "https://gist.github.com/somebody/abc123"

    plain = Blueprint(yaml_util.parse_yaml(raw), schema=BLUEPRINT_SCHEMA)

    tagged = Blueprint(yaml_util.parse_yaml(raw), schema=BLUEPRINT_SCHEMA)
    tagged.update_metadata(source_url=url)

    slashed = Blueprint(yaml_util.parse_yaml(raw), schema=BLUEPRINT_SCHEMA)
    slashed.update_metadata(source_url=url + "/")

    assert _fingerprint(plain) == _fingerprint(tagged) == _fingerprint(slashed)


def test_the_fingerprint_still_moves_when_the_blueprint_does() -> None:
    """So the checks above cannot pass by never changing at all."""
    raw = """
blueprint:
  name: Sensor Light
  domain: automation
triggers: []
"""
    before = Blueprint(yaml_util.parse_yaml(raw), schema=BLUEPRINT_SCHEMA)
    after = Blueprint(
        yaml_util.parse_yaml(raw.replace("Sensor Light", "Sensor Lights")),
        schema=BLUEPRINT_SCHEMA,
    )

    assert _fingerprint(before) != _fingerprint(after)


def test_the_fingerprint_notices_a_step_pointing_at_another_input() -> None:
    """`!input` arrives as an object, and objects flatten too far too easily.

    Both inputs are declared in both versions, so the `input:` block is
    identical and the only thing that moves is which one an action points at.
    Renaming an input instead would have changed that block as well, and then
    this would pass even if the reference were thrown away entirely.
    """
    raw = """
blueprint:
  name: Sensor Light
  domain: automation
  input:
    light:
      name: Light
    lamp:
      name: Lamp
triggers: []
actions:
  - action: light.turn_on
    target:
      entity_id: !input light
"""
    before = Blueprint(yaml_util.parse_yaml(raw), schema=BLUEPRINT_SCHEMA)
    after = Blueprint(
        yaml_util.parse_yaml(raw.replace("!input light", "!input lamp")),
        schema=BLUEPRINT_SCHEMA,
    )

    assert _fingerprint(before) != _fingerprint(after)


def test_the_fingerprint_notices_variables_swapping_places() -> None:
    """A `variables:` block is rendered one entry at a time.

    Earlier results are available to later ones, so the order of those keys is
    executable rather than decoration. Sorting keys before hashing, which is
    what the first version of this did, made a reordering that changes what a
    script does look like no change at all.
    """
    raw = """
blueprint:
  name: T
  domain: automation
triggers: []
actions:
  - variables:
      first: 1
      second: "{{ first }}"
"""
    swapped = """
blueprint:
  name: T
  domain: automation
triggers: []
actions:
  - variables:
      second: "{{ first }}"
      first: 1
"""
    before = Blueprint(yaml_util.parse_yaml(raw), schema=BLUEPRINT_SCHEMA)
    after = Blueprint(yaml_util.parse_yaml(swapped), schema=BLUEPRINT_SCHEMA)

    assert _fingerprint(before) != _fingerprint(after)


@pytest.mark.parametrize(
    ("one", "other"),
    [
        pytest.param(Input("light"), {"__input__": "light"}, id="input-vs-mapping"),
        pytest.param(Input("light"), ["input", "light"], id="input-vs-sequence"),
        pytest.param({"a": "b"}, [["a", "b"]], id="mapping-vs-pairs"),
        pytest.param(
            {"a": "b"}, [["map", [["a", ["str", "b"]]]]], id="mapping-vs-own-form"
        ),
        pytest.param("x", ["x"], id="string-vs-sequence"),
        pytest.param("1", 1, id="string-vs-number"),
        pytest.param({"a": "b", "c": "d"}, {"c": "d", "a": "b"}, id="order-swapped"),
        pytest.param({1: "a"}, {"1": "a"}, id="number-key-vs-string-key"),
        pytest.param({True: "a"}, {"True": "a"}, id="bool-key-vs-string-key"),
        pytest.param({1.5: "a"}, {"1.5": "a"}, id="float-key-vs-string-key"),
    ],
)
def test_the_encoding_keeps_different_things_apart(one: object, other: object) -> None:
    """Nothing may serialize the same as anything else it is not.

    Two blueprints that behave differently and fingerprint the same would be
    an update Spook never mentions, which is worse than one it mentions twice.
    A mapping somebody wrote by hand must not come out looking like an
    `!input`, an ordered mapping must not come out looking like the list of
    pairs it is encoded as, and swapping two keys must show.

    Tested on the encoding rather than through a pair of blueprints, because
    at that level it takes three separate mistakes at once to produce a
    collision, and a test that needs all three is a test that catches none.
    """
    assert _canonical(one) != _canonical(other)


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        pytest.param(Input("light"), "input", id="input"),
        pytest.param({"a": "b"}, "map", id="mapping"),
        pytest.param(["a"], "seq", id="sequence"),
        pytest.param("a", "str", id="string"),
        pytest.param(1, "value", id="number"),
    ],
)
def test_every_kind_of_value_says_what_it_is(value: object, kind: str) -> None:
    """Each kind carries its own tag, and that is what keeps them apart.

    Asserted on the shape rather than by finding two values that collide,
    because a collision needs several of these tags dropped at once. A test
    that only fails when three mistakes are made together catches none of
    them on its own.
    """
    assert _canonical(value)[0] == kind


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("a: 2026-01-01", id="date"),
        pytest.param("a: 2026-01-01 10:00:00", id="datetime"),
        pytest.param("a: !!binary aGk=", id="binary"),
        pytest.param("a: !!set {x: null, y: null}", id="set"),
    ],
)
def test_the_encoding_survives_what_yaml_hands_back(text: str) -> None:
    """YAML produces things JSON has never heard of.

    An unquoted date arrives as a `datetime.date`, and passing that to
    `json.dumps` raises `TypeError`, which took the whole round of checks down
    with it rather than one blueprint.
    """
    json.dumps(_canonical(yaml_util.parse_yaml(text)))


def test_a_date_and_the_same_date_written_out_are_not_the_same() -> None:
    """Rendering these as text must not let two kinds collide."""
    as_date = yaml_util.parse_yaml("a: 2026-01-01")
    as_string = yaml_util.parse_yaml('a: "2026-01-01"')

    assert _canonical(as_date) != _canonical(as_string)


def test_a_set_is_encoded_in_a_fixed_order() -> None:
    """Two runs of Home Assistant must fingerprint a `!!set` the same.

    A set has no order of its own and Python iterates one by hash, which
    depends on `PYTHONHASHSEED` and so differs between processes. Within a
    single test the order never varies, so this asserts the encoding is sorted
    rather than trying to catch a difference that cannot happen here. Without
    it a blueprint holding a `!!set` would report an update on some restarts
    and not others, which is the least debuggable kind of wrong.
    """
    encoded = _canonical(yaml_util.parse_yaml("a: !!set {x: null, y: null, a: null}"))
    members = encoded[1][0][1][1]

    assert members == sorted(members)


def test_a_whole_blueprint_holding_awkward_values_fingerprints() -> None:
    """The same values, but buried in action data where the schema is loosest.

    The checks above hand `_canonical` a value on its own. This goes through
    `_fingerprint` on a blueprint that would really load, because it was the
    round of checks that died on this and not the encoding in isolation.
    """
    text = """
blueprint:
  name: T
  domain: automation
triggers: []
actions:
  - action: notify.persistent_notification
    data:
      message: hi
      when: 2026-01-01
      at: 2026-01-01 10:00:00
      blob: !!binary aGk=
"""
    blueprint_with = Blueprint(yaml_util.parse_yaml(text), schema=BLUEPRINT_SCHEMA)
    fingerprint = _fingerprint(blueprint_with)
    assert fingerprint

    # A date and the text of that date are different values.
    quoted = Blueprint(
        yaml_util.parse_yaml(text.replace("when: 2026-01-01", 'when: "2026-01-01"')),
        schema=BLUEPRINT_SCHEMA,
    )
    assert _fingerprint(quoted) != fingerprint


def test_a_cyclic_alias_never_reaches_the_encoding() -> None:
    """The encoding recurses without tracking what it has seen.

    Which is safe only because Home Assistant's loader refuses a recursive
    node while parsing, long before any of this. Worth pinning, because if
    that ever changed the encoding would hit a `RecursionError` and
    `_read_files` catches only `OSError`, so one file would take the whole
    round of checks with it.
    """
    assert _normalize("a: &s [*s]") is None
    assert _normalize("a: &m {k: *m}") is None


def test_an_alias_fingerprints_the_same_as_writing_it_out() -> None:
    """A shared alias is two names for one value, not a cycle, and it parses.

    Two blueprints saying the same thing, one using an anchor and one spelling
    it out twice, are the same blueprint. The old fingerprint went through
    PyYAML's dumper, which writes anchors back out as `&id001`, so those two
    used to disagree.
    """
    aliased = """
blueprint:
  name: T
  domain: automation
triggers: []
actions:
  - action: light.turn_on
    target: &t {entity_id: light.a}
  - action: light.turn_off
    target: *t
"""
    written_out = """
blueprint:
  name: T
  domain: automation
triggers: []
actions:
  - action: light.turn_on
    target: {entity_id: light.a}
  - action: light.turn_off
    target: {entity_id: light.a}
"""
    one = Blueprint(yaml_util.parse_yaml(aliased), schema=BLUEPRINT_SCHEMA)
    other = Blueprint(yaml_util.parse_yaml(written_out), schema=BLUEPRINT_SCHEMA)

    assert _fingerprint(one) == _fingerprint(other)


async def test_the_name_is_the_blueprint_and_nothing_else(
    hass: HomeAssistant,
) -> None:
    """The updates page reads a row by the device it belongs to.

    These used to hang off one device called "Blueprints", so twenty rows all
    said "Blueprints" and none of them said which blueprint. Without a device
    the name is the blueprint's own.
    """
    write_by_hand(hass, "automation", "spooky.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    state = hass.states.get(_ENTITY)
    assert state
    assert state.attributes["friendly_name"] == "Spooky motion light"
    assert state.attributes["title"] == "Spooky motion light"


async def test_no_device_is_made_for_these(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A blueprint is a file. It has no firmware and it is not a device."""
    write_by_hand(hass, "automation", "spooky.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    assert hass.states.get(_ENTITY)
    # Iterated rather than looked up: mapping access on this is deprecated.
    assert not list(device_registry.devices)


async def test_the_old_blueprints_device_is_cleared_away(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Anybody who ran an earlier version has one of these sitting there.

    Dropping the device off the entities leaves it behind holding nothing, and
    a device that is not a device and has nothing on it is only something to
    wonder about later.

    Home Assistant deletes the registration of every entity on a device when
    the device goes, and both belong to the same config entry here, so this
    reaches for that. What it asserts is that it never happens: the entity is
    taken off the device first. Home Assistant would in fact hand the whole
    registration back the moment the same unique ID turned up again, a few
    lines further into the same setup, so nothing would be lost either way.
    The point is the churn. A dozen repairs re-inspect on any entity registry
    change, and this would tell them all that an entity had gone and come back
    for no reason at all.

    So the config entry is handed to the setup rather than made up on the
    spot. Under two entries Home Assistant never compares them as equal, this
    would not reach the removal at all, and it would pass while doing nothing.
    """
    entry = MockConfigEntry(domain="fake")
    entry.add_to_hass(hass)

    left_behind = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "blueprint")},
        manufacturer="Home Assistant",
        name="Blueprints",
    )
    was_there = entity_registry.async_get_or_create(
        "update",
        "fake",
        "blueprint_automation_spooky.yaml",
        config_entry=entry,
        device_id=left_behind.id,
        suggested_object_id="blueprints_spooky_motion_light",
    )
    entity_registry.async_update_entity(
        was_there.entity_id,
        icon="mdi:ghost",
        name="The one I renamed myself",
    )

    dropped: list[str] = []

    @callback
    def _note_what_goes(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        if event.data["action"] == "remove":
            dropped.append(event.data["entity_id"])

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _note_what_goes)

    write_by_hand(hass, "automation", "spooky.yaml", MOTION_LIGHT)
    await async_set_up(hass, entry=entry)

    assert device_registry.async_get(left_behind.id) is None
    assert not dropped

    kept = entity_registry.async_get(was_there.entity_id)
    assert kept is not None
    assert kept.device_id is None
    assert kept.name == "The one I renamed myself"
    assert kept.icon == "mdi:ghost"

    # And it is the entity that is actually there, rather than a registration
    # sitting next to one that came back under a name of its own.
    assert hass.states.get(was_there.entity_id)


async def test_a_registration_left_behind_by_a_deleted_blueprint_is_dropped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A blueprint deleted while Home Assistant was stopped tells nobody.

    The round that would have caught it compares against the entities of this
    run, and on the first round there are none, so without this the
    registration sits in the list for good with nothing behind it.

    Seeded in the shape the released version wrote it, on purpose: the whole
    point is reading what an older Spook left, so a literal is the only honest
    way to write it down.
    """
    entry = MockConfigEntry(domain="fake")
    entry.add_to_hass(hass)

    left_over = entity_registry.async_get_or_create(
        "update",
        "fake",
        "blueprint_automation_i_deleted_this.yaml",
        config_entry=entry,
        suggested_object_id="blueprints_something_i_deleted",
    )

    write_by_hand(hass, "automation", "spooky.yaml", MOTION_LIGHT)
    await async_set_up(hass, entry=entry)

    assert entity_registry.async_get(left_over.entity_id) is None

    # The blueprint that is there keeps everything it had.
    assert entity_registry.async_get(_ENTITY) is not None
    assert hass.states.get(_ENTITY)


async def test_a_domain_that_is_out_of_sight_keeps_its_registrations(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """A domain that has not registered says nothing about its blueprints.

    Reading that silence as "there are none" would take every registration it
    has, on a round that happened to land while the integration was still
    setting up. So the domains that were there to be asked are part of what a
    look reports, and a domain that was not is left alone entirely.
    """
    entry = MockConfigEntry(domain="fake")
    entry.add_to_hass(hass)

    write_by_hand(hass, "automation", "spooky.yaml", MOTION_LIGHT)
    await async_set_up(hass, entry=entry)

    out_of_sight = entity_registry.async_get_or_create(
        "update",
        "fake",
        "blueprint_script_gone_fishing.yaml",
        config_entry=entry,
        suggested_object_id="blueprints_gone_fishing",
    )

    without_scripts = {
        domain: item
        for domain, item in hass.data[BLUEPRINT_DOMAIN].items()
        if domain != "script"
    }
    with (
        patch.dict(hass.data, {BLUEPRINT_DOMAIN: without_scripts}),
        _source_says(MOTION_LIGHT),
    ):
        await _check(hass, freezer)

    assert entity_registry.async_get(out_of_sight.entity_id) is not None

    # And it was the looking away that saved it. With the domain back, the
    # same registration goes, which is the only way to know the round would
    # otherwise have taken it.
    with _source_says(MOTION_LIGHT):
        await _check(hass, freezer)

    assert entity_registry.async_get(out_of_sight.entity_id) is None


async def test_a_blueprint_that_will_not_load_keeps_its_registration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Home Assistant names a blueprint it could not load, and so it is there.

    Most likely somebody is halfway through editing it. Nothing can be read
    out of it to say whether it still comes from anywhere, and a file being
    unreadable is not a file being gone.
    """
    entry = MockConfigEntry(domain="fake")
    entry.add_to_hass(hass)

    mid_edit = entity_registry.async_get_or_create(
        "update",
        "fake",
        "blueprint_automation_halfway.yaml",
        config_entry=entry,
        suggested_object_id="blueprints_halfway",
    )

    write_by_hand(hass, "automation", "spooky.yaml", MOTION_LIGHT)
    write_by_hand(hass, "automation", "halfway.yaml", "nope: not a blueprint\n")
    await async_set_up(hass, entry=entry)

    assert entity_registry.async_get(mid_edit.entity_id) is not None


async def test_a_blueprint_that_dropped_its_source_loses_its_registration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Taking the source URL out is asking to be left alone.

    Which the round already honours for an entity it has. Done while Home
    Assistant was stopped it never had one, so the registration is the only
    thing left saying Spook was ever interested.
    """
    entry = MockConfigEntry(domain="fake")
    entry.add_to_hass(hass)

    on_its_own = entity_registry.async_get_or_create(
        "update",
        "fake",
        "blueprint_automation_on_its_own.yaml",
        config_entry=entry,
        suggested_object_id="blueprints_on_its_own",
    )

    write_by_hand(hass, "automation", "spooky.yaml", MOTION_LIGHT)
    write_by_hand(
        hass,
        "automation",
        "on_its_own.yaml",
        MOTION_LIGHT.replace("  source_url: {source}\n", ""),
    )
    await async_set_up(hass, entry=entry)

    assert entity_registry.async_get(on_its_own.entity_id) is None


async def test_a_registration_that_is_not_about_a_blueprint_is_left_alone(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Spook is free to put other updates on this config entry.

    Nothing here knows anything about those, and a tidy-up that cannot tell
    what a unique ID is about has no business touching it.
    """
    entry = MockConfigEntry(domain="fake")
    entry.add_to_hass(hass)

    somebody_elses = entity_registry.async_get_or_create(
        "update",
        "fake",
        "nothing_to_do_with_blueprints",
        config_entry=entry,
        suggested_object_id="spook_itself",
    )

    write_by_hand(hass, "automation", "spooky.yaml", MOTION_LIGHT)
    await async_set_up(hass, entry=entry)

    assert entity_registry.async_get(somebody_elses.entity_id) is not None


async def test_the_dialog_offers_to_keep_a_copy(
    hass: HomeAssistant,
) -> None:
    """Installing writes over whatever is there, so the offer has to be made.

    Home Assistant renders the tick box off the back of this flag and refuses
    a backup asked for without it, so the flag is the whole of the offer.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    assert (
        UpdateEntityFeature.BACKUP
        in hass.states.get(_ENTITY).attributes["supported_features"]
    )


async def test_a_copy_is_kept_when_one_was_asked_for(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """What is written over is gone, so the copy is the only way back."""
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    was_there = file.read_text(encoding="utf-8")
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY, "backup": True},
            blocking=True,
        )
    await hass.async_block_till_done()

    copies = _copies_beside(file)
    assert len(copies) == 1
    assert copies[0].read_text(encoding="utf-8") == was_there

    # Named after the file it is a copy of, and when. Deliberately not ending
    # in .yaml: Home Assistant globs those out of the blueprint folders and
    # would take the copy for a blueprint of its own.
    assert _COPY.match(copies[0].name)["of"] == "motion.yaml"

    # And the blueprint itself did get written.
    assert "to: 'off'" in file.read_text(encoding="utf-8")


async def test_no_copy_is_kept_when_none_was_asked_for(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The tick box is a question, not a formality."""
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY, "backup": False},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert _copies_beside(file) == []


async def test_only_the_newest_few_copies_are_kept(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Otherwise the folder fills up with every update anybody ever installed.

    Somebody opening it in a file editor has to be able to read it, and past
    three there is nothing being offered that the newest three do not.
    """
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    versions = [
        MOTION_LIGHT_CHANGED,
        MOTION_LIGHT_CHANGED_AGAIN,
        MOTION_LIGHT,
        MOTION_LIGHT_CHANGED,
    ]
    made: list[str] = []
    for version in versions:
        with _source_says(version):
            await _check(hass, freezer)
            await hass.services.async_call(
                "update",
                "install",
                {"entity_id": _ENTITY, "backup": True},
                blocking=True,
            )
        await hass.async_block_till_done()

        made.append(_copies_beside(file)[0].name)

    # Four installs, and each one left something different behind, so this is
    # counting four copies down to three rather than three copies twice.
    assert len(set(made)) == len(versions)

    kept = {copy.name for copy in _copies_beside(file)}
    assert len(kept) == _KEEP_COPIES

    # The oldest went and the newest stayed, which is the way round that
    # matters and the whole reason the stamp reads as it does.
    assert made[0] not in kept
    assert set(made[1:]) == kept


async def test_the_copies_of_another_blueprint_are_left_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A name can be the start of another name.

    `motion.yaml` is the front of `motion.yaml.old.yaml`, so anything matching
    on the front of a filename counts one blueprint's copies as another's and
    throws away somebody else's oldest.
    """
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)

    somebody_elses = [
        file.with_name(f"motion.yaml.old.yaml.2026-01-0{day}_120000.bak")
        for day in (1, 2, 3, 4)
    ]
    for copy in somebody_elses:
        copy.write_text("not mine", encoding="utf-8")

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": _ENTITY, "backup": True},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert all(copy.exists() for copy in somebody_elses)
    assert len(_copies_beside(file)) == 1


async def test_a_copy_that_cannot_be_made_stops_the_install(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Asked for a copy, did not get one, and wrote anyway.

    Which is the worst of both: the version that worked is gone and nothing
    was kept in its place.
    """
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    was_there = file.read_text(encoding="utf-8")
    await async_set_up(hass)

    with (
        _source_says(MOTION_LIGHT_CHANGED),
        patch(
            "custom_components.spook.ectoplasms.blueprint.update.shutil.copy2",
            side_effect=OSError("no room left"),
        ),
    ):
        await _check(hass, freezer)

        with pytest.raises(HomeAssistantError, match="no room left"):
            await hass.services.async_call(
                "update",
                "install",
                {"entity_id": _ENTITY, "backup": True},
                blocking=True,
            )

    assert file.read_text(encoding="utf-8") == was_there
    assert hass.states.get(_ENTITY).state == "on"


async def test_the_notes_say_where_the_two_differ(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A fingerprint on its own is an assertion: something changed, trust us.

    Whoever has to decide whether to install this is better off being told
    where to look, and "only the bit I never touch" is an answer as much as
    anything else is.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    assert "When it runs **changed**" in await _release_notes(client)


async def test_the_notes_name_an_input_that_was_added(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Which is the one difference that decides whether this can be installed.

    A new input nobody sets stops every automation on the blueprint from
    loading, so it is worth naming rather than lumping in with the rest of the
    metadata.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_WITH_NEW_INPUT):
        await _check(hass, freezer)

    assert "**New settings**: Wait time" in await _release_notes(client)


async def test_the_notes_say_when_only_the_order_changed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Every key the same, every value the same, and still not the same file.

    Order counts in a blueprint: a `variables:` block is rendered one entry at
    a time with the earlier ones already worked out. So this is a real
    difference, and saying "nothing differs" while offering an update would be
    the worst of both.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    swapped = MOTION_LIGHT.replace(
        "    motion_entity:\n      name: Motion sensor\n"
        "    light_target:\n      name: Light\n",
        "    light_target:\n      name: Light\n"
        "    motion_entity:\n      name: Motion sensor\n",
    )
    assert swapped != MOTION_LIGHT

    with _source_says(swapped):
        await _check(hass, freezer)

    assert "written in a different order" in await _release_notes(client)


async def test_the_notes_admit_when_the_copy_here_cannot_be_read(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Saying nothing would read as "nothing changed", which is not the same."""
    file = async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    file.write_text("{{{ not yaml", encoding="utf-8")

    assert "cannot say what this changes" in await _release_notes(client)


async def test_the_notes_count_settings_once_there_are_too_many_to_read(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Eighty names is not a release note, it is a wall.

    Past a few, what somebody needs to know is how much of it changed, and the
    names are in the blueprint for whoever wants them.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    plenty = _HOW_MANY_TO_NAME + 5
    rewritten = MOTION_LIGHT.replace(
        "    light_target:\n      name: Light\n",
        "    light_target:\n      name: Light\n"
        + "".join(
            f"    extra_{number}:\n      name: Extra {number}\n"
            f"      default: {number}\n"
            for number in range(plenty)
        ),
    )

    with _source_says(rewritten):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert f"**New settings**: {plenty}" in notes

    # The summary counts them. The difference itself is further down and does
    # name every one, which is what it is for.
    summary = notes.split("<details>")[0]
    assert "Extra 0" not in summary


def test_a_source_url_of_its_own_is_not_a_difference() -> None:
    """Whoever imported a blueprint put that address in, not its author.

    It is also the address this was just fetched from, so an author who moved
    their blueprint has not changed it. The fingerprint leaves it out and this
    has to leave it out the same way, or the dialog would name a difference
    that never made an update appear.
    """
    here = _normalize(MOTION_LIGHT.format(source="https://example.com/one"))
    there = _normalize(MOTION_LIGHT.format(source="https://example.com/two"))

    assert not _changes(here, there)


def test_what_a_change_to_the_trigger_is_called() -> None:
    """One key of the file, and not a word of the file's own vocabulary.

    A blueprint writes `trigger:` or `triggers:` depending on when it was
    written, and neither is what somebody reading a dialog wants to be told.
    """
    here = _normalize(MOTION_LIGHT.format(source=SOURCE))
    there = _normalize(MOTION_LIGHT_CHANGED.format(source=SOURCE))

    assert _in_words(_changes(here, there)) == ["When it runs **changed**"]


async def test_the_notes_say_when_the_whole_file_only_moved_around(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Nothing to name, because nothing in it is what changed.

    Naming the file itself in a list of paths would read as a path, so this is
    a sentence instead.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    # The same keys at the top of the file, the other way round.
    swapped = MOTION_LIGHT.replace(
        "trigger:\n  - platform: state\n    entity_id: !input motion_entity\n"
        '    to: "on"\naction:\n  - service: light.turn_on\n'
        "    entity_id: !input light_target\n",
        "action:\n  - service: light.turn_on\n"
        "    entity_id: !input light_target\n"
        "trigger:\n  - platform: state\n    entity_id: !input motion_entity\n"
        '    to: "on"\n',
    )
    assert swapped != MOTION_LIGHT

    with _source_says(swapped):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "written in a different order" in notes


async def test_a_rename_that_keeps_the_label_still_reads_as_two_things(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The one rename that says nothing while breaking everything.

    An author who changes the key an input is stored under and leaves its
    label alone gives two settings that read the same. Whatever somebody set
    is under the old key and the new version never looks there, so the key has
    to come along or the dialog says "Motion sensor is new, Motion sensor is
    gone" and means it.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT.replace("motion_entity", "motion_sensor")):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "**New settings**: Motion sensor (`motion_sensor`)" in notes
    assert "**Settings taken away**: Motion sensor (`motion_entity`)" in notes


async def test_a_home_assistant_it_needs_is_only_said_once(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The refusal already names the version and says Spook will not write it.

    Saying it again above reads as two separate problems with the same
    blueprint.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_FROM_THE_FUTURE):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "will not install it" in notes
    assert "It now asks for Home Assistant" not in notes


async def test_the_notes_say_nothing_is_built_on_it(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Which is worth saying out loud, because it makes the decision easy.

    An update that cannot reach anything is one somebody can install without
    reading another word.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    assert "No automations are using this blueprint." in await _release_notes(client)


async def test_the_notes_name_the_one_automation_built_on_it(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """With a link to it.

    What an update is about to touch is the first question anybody asks, and
    the answer used to be a shrug.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    await async_add_automation(hass, "Hallway light", "motion.yaml", _MOTION_INPUTS)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "**The following automation is using this blueprint:**" in notes
    assert "- [Hallway light](/config/automation/edit/hallway_light)" in notes


async def test_the_notes_count_the_automations_built_on_it(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """And put them in an order somebody can read."""
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    # Three of them, written in an order that is neither the one they should
    # come out in nor its reverse. With two, handing them back backwards would
    # land on the right answer by accident and this would pass while sorting
    # nothing.
    written = ["Porch light", "Attic light", "Hallway light"]
    async_write_config(
        hass,
        [
            {
                "id": alias.split()[0].lower(),
                "alias": alias,
                "use_blueprint": {"path": "motion.yaml", "input": _MOTION_INPUTS},
            }
            for alias in written
        ],
    )
    await hass.services.async_call("automation", "reload", blocking=True)
    await hass.async_block_till_done()

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "**The following 3 automations are using this blueprint:**" in notes

    assert [notes.index(alias) for alias in sorted(written)] == sorted(
        notes.index(alias) for alias in written
    )


async def test_an_automation_with_no_id_gets_the_overview_page(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Written in YAML without an `id:`, so there is no editor to open.

    Linking to `/config/automation/edit/None` sends somebody to a page that
    cannot load, which is worse than sending them to the list.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    async_write_config(
        hass,
        [
            {
                "alias": "Nameless in YAML",
                "use_blueprint": {"path": "motion.yaml", "input": _MOTION_INPUTS},
            },
        ],
    )
    await hass.services.async_call("automation", "reload", blocking=True)
    await hass.async_block_till_done()

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "- [Nameless in YAML](/config/automation/dashboard)" in notes
    assert "None" not in notes


async def test_the_notes_call_a_script_a_script(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A script blueprint is used by scripts, and they live somewhere else."""
    async_write_blueprint(hass, "script", "notify.yaml", A_SCRIPT_BLUEPRINT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    await async_add_script(hass, "shout", "notify.yaml", _SHOUT_INPUTS)

    with _source_says(A_SCRIPT_BLUEPRINT_CHANGED):
        await _check(hass, freezer)

    notes = await _release_notes(client, "update.spooky_confirmable_notification")
    assert "**The following script is using this blueprint:**" in notes
    assert "/config/script/edit/shout" in notes


async def test_the_notes_carry_the_difference_itself(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Collapsed, because most people want the sentence and not this.

    Home Assistant's markdown keeps `details` and `summary` and parses a fenced
    block inside them, so this arrives as something to open rather than a wall
    to scroll past.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "<details>" in notes
    assert "<summary>Line by line</summary>" in notes
    assert "```diff" in notes
    assert "+  to: 'off'" in notes


async def test_the_difference_holds_nothing_but_the_difference(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Written by hand, so the file on disk is in its author's own layout.

    Home Assistant writes a blueprint back out in its own formatting, so a
    file somebody edited themselves and a freshly fetched one differ in
    indentation, quoting and line breaks before either of them differs in
    anything that matters. Eleven lines of that on this very blueprint.

    So both sides go through the same dumper first, and what is left is the one
    line that moved.
    """
    write_by_hand(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    with _source_says(MOTION_LIGHT_CHANGED):
        await _check(hass, freezer)

    notes = await _release_notes(client)

    # The difference itself, not the bullets above it: those start with a
    # hyphen too, being a markdown list.
    block = notes.split("```diff")[1].split("```")[0]
    moved = [
        line
        for line in block.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]

    assert moved == ["-  to: 'on'", "+  to: 'off'"]


async def test_a_difference_too_long_to_send_is_cut_short(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """All of it travels to the dialog whether anybody opens it or not.

    A blueprint of half a megabyte that has been rewritten runs to thousands of
    lines, and sending those to say "quite a lot changed" is not a trade worth
    making.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    plenty = MOTION_LIGHT.replace(
        "    light_target:\n      name: Light\n",
        "    light_target:\n      name: Light\n"
        + "".join(
            f"    extra_{number}:\n      name: Extra {number}\n"
            f"      default: {number}\n"
            for number in range(_HOW_MANY_LINES)
        ),
    )

    with _source_says(plenty):
        await _check(hass, freezer)

    notes = await _release_notes(client)
    assert "more lines" in notes
    assert len(notes.splitlines()) < _HOW_MANY_LINES * 2


async def test_what_spook_will_not_do_comes_before_anything_else(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Everything else is context for a decision already taken.

    Burying "this cannot be installed" under three paragraphs of what changed
    asks somebody to read all of it before finding out none of it matters yet.

    A Home Assistant version it needs is the one thing Spook does refuse over,
    because nothing anybody does to their own automations gets them out of it.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    await async_add_automation(hass, "Landing light", "motion.yaml", _MOTION_INPUTS)

    with _source_says(MOTION_LIGHT_FROM_THE_FUTURE):
        await _check(hass, freezer)

    notes = await _release_notes(client)

    assert notes.startswith("<ha-alert alert-type='error'>")
    assert notes.index("will not install it") < notes.index("carry no changelog")
    assert notes.index("will not install it") < notes.index("Imported from")

    # And the version is said once. The refusal names it, so the summary above
    # leaves it out rather than reading as a second problem.
    assert "It now asks for Home Assistant" not in notes


async def test_what_an_update_will_cost_comes_before_anything_else(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Same reasoning for a warning as for a refusal.

    Whether an update stops the automations built on it is the headline, and
    people do not read to the bottom for a headline.
    """
    async_write_blueprint(hass, "automation", "motion.yaml", MOTION_LIGHT)
    await async_set_up(hass)
    client = await hass_ws_client(hass)

    await async_add_automation(hass, "Landing light", "motion.yaml", _MOTION_INPUTS)

    with _source_says(MOTION_LIGHT_WITH_NEW_INPUT):
        await _check(hass, freezer)

    notes = await _release_notes(client)

    assert notes.startswith("<ha-alert alert-type='warning'>")
    assert notes.index("stop what is listed below") < notes.index("Compared with")
