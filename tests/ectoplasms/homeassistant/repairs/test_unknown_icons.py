"""Tests for the repair about unknown icons in settings."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
import threading
from typing import TYPE_CHECKING, Any

from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.core_config import DATA_CUSTOMIZE
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    entity_registry as er,
    floor_registry as fr,
    issue_registry as ir,
    label_registry as lr,
)
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook import icon_checking
from custom_components.spook.ectoplasms.homeassistant.repairs.unknown_icons import (
    SpookRepair,
)
from custom_components.spook.repairs import CouldNotLook
import pytest
from tests.icon_helpers import (
    ICON_NAMES,
    ICON_VERSION,
    install_frontend,
    uninstall_frontend,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant

_ISSUE = "unknown_icons_unknown_icons"


async def _async_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> str | None:
    """Inspect, and return the list of icons the issue reports, if any."""
    await SpookRepair(hass).async_inspect()
    if (issue := async_issue_about(issue_registry, _ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["icons"]


async def _async_could_not_look(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Inspect, and see the repair say it could not look, reporting nothing."""
    with pytest.raises(CouldNotLook, match="The icons of the frontend"):
        await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, _ISSUE) is None


def _area_with_icon(hass: HomeAssistant, icon: str) -> None:
    """Give an area this icon."""
    ar.async_get(hass).async_create("Kitchen", icon=icon)


async def test_every_place_with_an_icon_is_looked_at(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every setting that holds an icon is read, and said where it is."""
    install_frontend(monkeypatch, tmp_path)

    entity_registry = er.async_get(hass)
    lamp = entity_registry.async_get_or_create("light", "demo", "lamp")
    entity_registry.async_update_entity(lamp.entity_id, icon="mdi:lamp-ghost")
    sofa = entity_registry.async_get_or_create("light", "demo", "sofa")
    entity_registry.async_update_entity(sofa.entity_id, icon="mdi:sofa")

    assert await async_setup_component(
        hass,
        "input_boolean",
        {
            "input_boolean": {
                "porch": {"icon": "mdi:porch-ghost"},
                "living": {"icon": "mdi:sofa"},
            }
        },
    )
    assert await async_setup_component(
        hass,
        "zone",
        {
            "zone": [
                {
                    "name": "Office",
                    "latitude": 52.37,
                    "longitude": 4.89,
                    "icon": "mdi:office-ghost",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    ar.async_get(hass).async_create("Kitchen", icon="mdi:kitchen-ghost")
    ar.async_get(hass).async_create("Living room", icon="mdi:sofa")
    fr.async_get(hass).async_create("Attic", icon="mdi:attic-ghost")
    lr.async_get(hass).async_create("Holiday", icon="mdi:holiday-ghost")
    # The same name in two scopes, told apart by the scope.
    cr.async_get(hass).async_create(
        scope="automation", name="Night", icon="mdi:night-ghost"
    )
    cr.async_get(hass).async_create(
        scope="script", name="Night", icon="mdi:night-ghost"
    )
    hass.data[DATA_CUSTOMIZE] = EntityValues(
        exact={
            "light.porch": {"icon": "mdi:customize-ghost"},
            "light.hall": {"icon": "mdi:home"},
        },
        domain={"sensor": {"icon": "mdi:domain-ghost"}},
    )

    reported = await _async_reported(hass, issue_registry)

    assert reported == "\n".join(
        [
            f"- `mdi:lamp-ghost` on the entity `{lamp.entity_id}`",
            "- `mdi:porch-ghost` on the helper `input_boolean.porch`",
            "- `mdi:office-ghost` on the zone `zone.office`",
            "- `mdi:kitchen-ghost` on the area Kitchen",
            "- `mdi:attic-ghost` on the floor Attic",
            "- `mdi:holiday-ghost` on the label Holiday",
            "- `mdi:night-ghost` on the category Night (automation)",
            "- `mdi:night-ghost` on the category Night (script)",
            "- `mdi:customize-ghost` in `customize:` for `light.porch`",
            "- `mdi:domain-ghost` in `customize_domain:` for `sensor`",
        ]
    )


async def test_an_icon_covered_in_the_entity_settings_says_so(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A zone's own icon is still reported under another one, and says where.

    The icon picked in the entity settings is shown in its place nearly
    everywhere, but the zone keeps its own, and the list of zones still
    draws that one. #2058.
    """
    install_frontend(monkeypatch, tmp_path)
    hass_storage["zone"] = {
        "key": "zone",
        "version": 1,
        "data": {
            "items": [
                {
                    "id": "work",
                    "name": "Work",
                    "latitude": 52.37,
                    "longitude": 4.89,
                    "radius": 100,
                    "passive": False,
                    "icon": "mdi:work-ghost",
                }
            ]
        },
    }
    assert await async_setup_component(hass, "zone", {})
    await hass.async_block_till_done()

    repair = SpookRepair(hass)

    async def _reported() -> str:
        await repair._async_inspect_with_cleanup()  # noqa: SLF001
        issue = async_issue_about(issue_registry, _ISSUE)
        assert issue
        assert issue.translation_placeholders
        return issue.translation_placeholders["icons"]

    assert await _reported() == "- `mdi:work-ghost` on the zone `zone.work`"

    er.async_get(hass).async_update_entity("zone.work", icon="mdi:sofa")

    assert await _reported() == (
        "- `mdi:work-ghost` on the zone `zone.work` itself, "
        "covered by the icon in its entity settings"
    )


async def test_an_ignored_icon_stays_ignored_when_it_gets_covered(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Picking or clearing an icon in the entity settings is no new finding.

    The unknown icon and where it is set stay the same, so somebody who
    ignored the issue is not shown it again.
    """
    install_frontend(monkeypatch, tmp_path)
    hass_storage["zone"] = {
        "key": "zone",
        "version": 1,
        "data": {
            "items": [
                {
                    "id": "work",
                    "name": "Work",
                    "latitude": 52.37,
                    "longitude": 4.89,
                    "radius": 100,
                    "passive": False,
                    "icon": "mdi:work-ghost",
                }
            ]
        },
    }
    assert await async_setup_component(hass, "zone", {})
    await hass.async_block_till_done()

    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    ir.async_ignore_issue(hass, issue.domain, issue.issue_id, ignore=True)

    entity_registry = er.async_get(hass)
    for icon in ("mdi:sofa", None):
        entity_registry.async_update_entity("zone.work", icon=icon)
        await repair._async_inspect_with_cleanup()  # noqa: SLF001

        still = async_issue_about(issue_registry, _ISSUE)
        assert still
        assert still.issue_id == issue.issue_id
        assert still.dismissed_version is not None


async def test_a_name_that_reads_like_the_note_is_its_own_finding(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An area named after the note on a covered icon keeps its name whole.

    The note is no part of what tells one finding from another. Taking it
    off the end of a line would also take it off a name somebody gave.
    """
    install_frontend(monkeypatch, tmp_path)
    covered = "Kitchen itself, covered by the icon in its entity settings"
    ar.async_get(hass).async_create("Kitchen", icon="mdi:kitchen-ghost")
    ar.async_get(hass).async_create(covered, icon="mdi:kitchen-ghost")

    repair = SpookRepair(hass)
    found: list[list[str]] = []
    monkeypatch.setattr(
        repair,
        "async_create_issue",
        lambda **issue: found.append(issue["references"]),
    )
    await repair.async_inspect()

    assert found == [
        [
            "mdi:kitchen-ghost on the area Kitchen",
            f"mdi:kitchen-ghost on the area {covered}",
        ]
    ]


async def test_the_issue_says_which_version_of_the_icons(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An icon newer than the frontend's is a common cause, so it says."""
    install_frontend(monkeypatch, tmp_path)
    _area_with_icon(hass, "mdi:kitchen-ghost")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["version"] == ICON_VERSION


async def test_a_near_miss_suggests_the_icon_it_meant(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A typo one letter off, or a name in the wrong case, gets a suggestion."""
    install_frontend(monkeypatch, tmp_path)
    ar.async_get(hass).async_create("Kitchen", icon="mdi:lightbulb-outlin")
    ar.async_get(hass).async_create("Hall", icon="mdi:Sofa")

    reported = await _async_reported(hass, issue_registry)

    assert reported
    assert reported.splitlines() == [
        (
            "- `mdi:lightbulb-outlin` (did you mean `mdi:lightbulb-outline`?)"
            " on the area Kitchen"
        ),
        "- `mdi:Sofa` (did you mean `mdi:sofa`?) on the area Hall",
    ]


@pytest.mark.parametrize(
    "icon",
    [
        # On the list.
        "mdi:lightbulb",
        # The older prefixes, read from the same list, are left alone.
        "hass:lightbulb-ghost",
        "hassio:lightbulb-ghost",
        "hademo:lightbulb-ghost",
        # A set somebody added, which Spook has no list of.
        "phu:hue-ghost",
        # The frontend does not take `MDI` for the MDI prefix either.
        "MDI:lightbulb-ghost",
        # Templates, whatever they turn into.
        "mdi:{{ states('input_text.icon') }}",
        "mdi:[[[ return 'lightbulb' ]]]",
        "mdi:${icon}",
        # Drawn by the frontend from its own code, not from the list.
        "mdi:home-assistant",
        "mdi:esphome",
        # The frontend only reads up to a second colon.
        "mdi:lightbulb:ghost",
        # No name: the frontend draws nothing and does not look.
        "mdi:",
    ],
)
async def test_what_is_not_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    icon: str,
) -> None:
    """Only an `mdi:` name the frontend would go looking for is judged."""
    install_frontend(monkeypatch, tmp_path)
    _area_with_icon(hass, icon)

    assert await _async_reported(hass, issue_registry) is None


async def test_no_frontend_means_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the frontend's list there is nothing to tell icons apart by."""
    uninstall_frontend(monkeypatch)
    _area_with_icon(hass, "mdi:kitchen-ghost")

    await _async_could_not_look(hass, issue_registry)


async def test_an_empty_list_means_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A frontend built for development ships the list empty."""
    install_frontend(monkeypatch, tmp_path, names=())
    _area_with_icon(hass, "mdi:kitchen-ghost")

    await _async_could_not_look(hass, issue_registry)


async def test_a_frontend_without_the_list_means_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A development build leaves the icon files out altogether."""
    folder = install_frontend(monkeypatch, tmp_path)
    (folder / "iconMetadata.json").unlink()
    _area_with_icon(hass, "mdi:kitchen-ghost")

    await _async_could_not_look(hass, issue_registry)


async def test_a_list_with_a_part_missing_means_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Half a list would report every icon in the other half."""
    folder = install_frontend(monkeypatch, tmp_path)
    (folder / "chunk1.json").unlink()
    _area_with_icon(hass, "mdi:lightbulb")

    await _async_could_not_look(hass, issue_registry)


async def test_a_list_with_an_empty_part_means_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty part is a broken one, and its names would all look unknown."""
    folder = install_frontend(monkeypatch, tmp_path)
    (folder / "chunk1.json").write_text("{}")
    _area_with_icon(hass, "mdi:sofa")

    await _async_could_not_look(hass, issue_registry)


async def test_every_part_of_the_list_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An icon from the last part is known, not only those from the first."""
    install_frontend(monkeypatch, tmp_path)
    _area_with_icon(hass, "mdi:thermometer")

    assert await _async_reported(hass, issue_registry) is None


async def test_the_list_is_read_once(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The frontend cannot change without a restart, so it is read once."""
    folder = install_frontend(monkeypatch, tmp_path)
    _area_with_icon(hass, "mdi:kitchen-ghost")
    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, _ISSUE)

    # Read again, this would find no list, judge nothing and clear the issue.
    (folder / "iconMetadata.json").unlink()
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert async_issue_about(issue_registry, _ISSUE)


async def test_icons_that_cannot_be_read_keep_what_was_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test no list to judge by is no icon that is fine now.

    The icon in the settings is the same as before. A start with a frontend
    built for development has no list, and found the issue from before up.
    Clearing it would say the icon is drawn.
    """
    folder = install_frontend(monkeypatch, tmp_path)
    _area_with_icon(hass, "mdi:kitchen-ghost")
    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, _ISSUE)

    # The list is read once per run, so it is gone the way a start finds it.
    (folder / "iconMetadata.json").unlink()
    hass.data.pop(icon_checking.DATA_MDI_ICONS)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert async_issue_about(issue_registry, _ISSUE)

    # Readable again, and judged as usual: the icon is in this list.
    install_frontend(monkeypatch, tmp_path / "fixed", (*ICON_NAMES, "kitchen-ghost"))
    hass.data.pop(icon_checking.DATA_MDI_ICONS)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert async_issue_about(issue_registry, _ISSUE) is None


@pytest.mark.parametrize("work", ["_load_mdi_icons", "_suggestions"])
async def test_the_heavy_lifting_is_done_off_the_event_loop(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    work: str,
) -> None:
    """Reading the files and comparing against every name stay off the loop."""
    install_frontend(monkeypatch, tmp_path)
    _area_with_icon(hass, "mdi:lightbulb-outlin")

    original = getattr(icon_checking, work)
    threads: list[int] = []

    def _record_thread(*args: Any) -> Any:
        threads.append(threading.get_ident())
        return original(*args)

    monkeypatch.setattr(icon_checking, work, _record_thread)

    assert await _async_reported(hass, issue_registry)
    assert threads
    assert hass.loop_thread_id not in threads


async def test_a_fixed_icon_clears_the_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Once the icon exists, the issue goes."""
    install_frontend(monkeypatch, tmp_path)
    area_registry = ar.async_get(hass)
    area = area_registry.async_create("Kitchen", icon="mdi:kitchen-ghost")
    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, _ISSUE)

    area_registry.async_update(area.id, icon="mdi:home")
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert async_issue_about(issue_registry, _ISSUE) is None


async def test_a_helper_given_another_icon_is_looked_at_again(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Changing a helper's icon changes its entity, and no registry hears it."""
    install_frontend(monkeypatch, tmp_path)
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"porch": {"icon": "mdi:home"}}}
    )
    repair = SpookRepair(hass)
    await repair.async_activate()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, _ISSUE) is None

    entity = hass.data[DATA_INSTANCES]["input_boolean"].get_entity(
        "input_boolean.porch"
    )
    await entity.async_update_config({"id": "porch", "icon": "mdi:porch-ghost"})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    assert async_issue_about(issue_registry, _ISSUE)

    await repair.async_deactivate()
