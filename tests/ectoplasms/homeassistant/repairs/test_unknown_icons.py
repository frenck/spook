"""Tests for the repair about unknown icons in settings."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
import threading
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.core_config import DATA_CUSTOMIZE
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    entity_registry as er,
    floor_registry as fr,
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
import pytest
from tests.icon_helpers import ICON_VERSION, install_frontend, uninstall_frontend
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

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

    assert await _async_reported(hass, issue_registry) is None


async def test_an_empty_list_means_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A frontend built for development ships the list empty."""
    install_frontend(monkeypatch, tmp_path, names=())
    _area_with_icon(hass, "mdi:kitchen-ghost")

    assert await _async_reported(hass, issue_registry) is None


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

    assert await _async_reported(hass, issue_registry) is None


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

    assert await _async_reported(hass, issue_registry) is None


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

    assert await _async_reported(hass, issue_registry) is None


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
