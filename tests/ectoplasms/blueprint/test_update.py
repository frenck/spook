"""Tests for the update entities Spook puts on imported blueprints."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.core import CoreState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import DATA_INSTANCES
import aiohttp
import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.spook.ectoplasms.blueprint import update as update_module
from custom_components.spook.ectoplasms.blueprint.update import (
    _CHECK_INTERVAL,
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
    async_add_script,
    async_set_up,
    async_write_blueprint,
    examples_are_on_disk,
    imported_from,
    write_by_hand,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from freezegun.api import FrozenDateTimeFactory
    from pytest_homeassistant_custom_component.typing import (
        MockHAClientWebSocket,
        WebSocketGenerator,
    )

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er

_ENTITY = "update.blueprints_spooky_motion_light"
_FETCH = "custom_components.spook.ectoplasms.blueprint.update.fetch_blueprint_from_url"
_BOTH_OF_THEM = 2
_NOBODY_SAW_IT_COMING = "something nobody saw coming"
_ENOUGH_ROUNDS_TO_JUDGE = 8


def _source_says(raw: str, *, source: str = SOURCE):  # noqa: ANN202
    """Make the importer hand back this blueprint."""
    return patch(_FETCH, return_value=imported_from(raw, source=source))


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

    # And the one that was mid-fetch when the rug went does not put a live
    # state back over the unavailable one that unloading left.
    assert all(
        hass.states.get(entity_id).state == "unavailable"
        for entity_id in hass.states.async_entity_ids("update")
    ), "something wrote a state back after being taken away"


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


def _entity(hass: HomeAssistant) -> BlueprintUpdateEntity:
    """Return the update entity itself, for what the dialog cannot reach."""
    return hass.data[DATA_INSTANCES]["update"].get_entity(_ENTITY)


async def _release_notes(client: MockHAClientWebSocket) -> str:
    """Ask for the release notes the way the dialog does."""
    await client.send_json_auto_id(
        {"type": "update/release_notes", "entity_id": _ENTITY},
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
    assert "alert-type='error'" in notes
    assert "automation.landing_light" in notes
    assert "wait_time" in notes


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

    entity_id = "update.blueprints_spooky_confirmable_notification"
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


async def test_a_script_that_would_be_left_short_stops_the_install(
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

    entity_id = "update.blueprints_spooky_confirmable_notification"
    with _source_says(A_SCRIPT_BLUEPRINT_WITH_NEW_INPUT):
        await _check(hass, freezer)

        with pytest.raises(HomeAssistantError, match="title"):
            await hass.services.async_call(
                "update",
                "install",
                {"entity_id": entity_id},
                blocking=True,
            )

    assert file.read_text(encoding="utf-8") == before


async def test_a_consumer_that_cannot_be_read_stops_the_install(
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

        with pytest.raises(HomeAssistantError, match="landing_light"):
            await hass.services.async_call(
                "update",
                "install",
                {"entity_id": _ENTITY},
                blocking=True,
            )

    assert file.read_text(encoding="utf-8") == before


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


async def test_an_update_that_would_not_load_is_refused(
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

        with pytest.raises(HomeAssistantError, match="would not load"):
            await hass.services.async_call(
                "update",
                "install",
                {"entity_id": _ENTITY},
                blocking=True,
            )

    assert file.read_text(encoding="utf-8") == before
    assert hass.states.get("automation.landing_light") is not None


async def test_a_script_update_that_would_not_load_is_refused(
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

    entity_id = "update.blueprints_spooky_confirmable_notification"
    with _source_says(A_SCRIPT_BLUEPRINT_WITH_A_BAD_STEP):
        await _check(hass, freezer)

        with pytest.raises(HomeAssistantError, match="would not load"):
            await hass.services.async_call(
                "update",
                "install",
                {"entity_id": entity_id},
                blocking=True,
            )

    assert file.read_text(encoding="utf-8") == before
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

    assert "alert-type='error'" in notes
    assert "automation.landing_light" in notes
    assert "would not load" in notes

    # And the heading over that list says nothing about inputs. There are
    # three ways onto it, and blaming the commonest of them sends somebody off
    # setting inputs that were never the trouble.
    heading = notes.partition("<ha-alert alert-type='error'>")[2].partition(
        "</ha-alert>",
    )[0]
    assert "input" not in heading, heading
