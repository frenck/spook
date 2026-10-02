"""Tests for remembering what somebody said to leave alone."""

# A repair cleans up after itself in a private method, and that is exactly
# where an ignore used to get lost.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from custom_components.spook.const import DOMAIN
from custom_components.spook.dismissals import (
    DATA_DISMISSALS,
    STORAGE_KEY,
    async_setup_dismissals,
)
from custom_components.spook.repairs import AbstractSpookRepair, _RemoveOrIgnoreFixFlow

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant


class HauntedScriptRepair(AbstractSpookRepair):
    """Report whatever is currently broken in the one script there is."""

    domain = "mock"
    repair = "mock_repair"
    automatically_clean_up_issues = True

    findings: set[str]
    name: str

    def __init__(self, hass: HomeAssistant) -> None:
        """Start with nothing broken."""
        super().__init__(hass)
        self.findings = set()
        self.name = "Haunted"

    async def async_inspect(self) -> None:
        """Report the findings, if there are any."""
        if self.findings:
            self.async_create_issue(
                issue_id="script.haunted",
                references=self.findings,
                translation_placeholders={
                    "entities": ", ".join(sorted(self.findings)),
                    "name": self.name,
                },
            )


def _issues(issue_registry: ir.IssueRegistry) -> list[ir.IssueEntry]:
    """Return every issue Spook has up."""
    return [
        entry
        for (domain, _issue_id), entry in issue_registry.issues.items()
        if domain == DOMAIN
    ]


def _the_one_issue(issue_registry: ir.IssueRegistry) -> ir.IssueEntry:
    """Return the single issue there is, and insist there is one."""
    issues = _issues(issue_registry)
    assert len(issues) == 1, f"expected one issue, found {len(issues)}"
    return issues[0]


async def _look(repair: HauntedScriptRepair, findings: set[str]) -> None:
    """Have the repair look, finding these."""
    repair.findings = findings
    await repair._async_inspect_with_cleanup()


async def _ignore_what_is_up(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Press ignore on the one issue there is."""
    ir.async_ignore_issue(
        hass, DOMAIN, _the_one_issue(issue_registry).issue_id, ignore=True
    )


async def _set_up(hass: HomeAssistant) -> Callable[[], None]:
    """Set dismissals up the way Spook does on start."""
    return await async_setup_dismissals(hass)


async def test_a_shorter_list_stays_ignored(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test one finding going away does not bring back the rest.

    Ignore two missing lights, get one of them back, and the other one used to
    come up again as if nobody had ever seen it.
    """
    await _set_up(hass)
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a", "light.b"})
    await _ignore_what_is_up(hass, issue_registry)

    await _look(repair, {"light.a"})

    issue = _the_one_issue(issue_registry)
    assert issue.translation_placeholders == {"entities": "light.a", "name": "Haunted"}
    assert issue.dismissed_version is not None, "light.a came back up"


async def test_gone_for_a_moment_stays_ignored(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a round that finds nothing does not cost the ignore.

    Reloading an automation takes it away before it puts it back, and a look
    in between finds nothing at all. Clearing up after that look took the
    ignored issue, and its ignore with it.
    """
    await _set_up(hass)
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a"})
    await _ignore_what_is_up(hass, issue_registry)

    await _look(repair, set())
    assert not _issues(issue_registry)

    await _look(repair, {"light.a"})

    assert _the_one_issue(issue_registry).dismissed_version is not None


async def test_something_new_is_news(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an ignore covers what was ignored, and nothing after it. #1395."""
    await _set_up(hass)
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a"})
    await _ignore_what_is_up(hass, issue_registry)

    await _look(repair, {"light.a", "light.new"})

    assert _the_one_issue(issue_registry).dismissed_version is None


async def test_ignoring_survives_a_restart(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test the decision is on disk, not only in memory."""
    unload = await _set_up(hass)
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a", "light.b"})
    await _ignore_what_is_up(hass, issue_registry)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()
    assert hass_storage[STORAGE_KEY]["data"] == {
        "mock_repair": {"script.haunted": ["light.a", "light.b"]}
    }

    # A restart: nothing in memory, and nothing left on the issues either.
    unload()
    hass.data.pop(DATA_DISMISSALS)
    for issue in _issues(issue_registry):
        ir.async_delete_issue(hass, DOMAIN, issue.issue_id)
    await _set_up(hass)

    await _look(HauntedScriptRepair(hass), {"light.b"})

    assert _the_one_issue(issue_registry).dismissed_version is not None


async def test_a_reload_before_it_is_written_loses_nothing(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_storage: dict[str, Any],
) -> None:
    """Test reloading Spook inside the save delay keeps the latest ignore.

    Writing waits a few seconds. Reading the disk again on reload would start
    from before the ignore, and the old copy writing late would race the new.
    """
    unload = await _set_up(hass)
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a", "light.b"})
    await _ignore_what_is_up(hass, issue_registry)

    unload()
    for issue in _issues(issue_registry):
        ir.async_delete_issue(hass, DOMAIN, issue.issue_id)
    await _set_up(hass)
    await _look(HauntedScriptRepair(hass), {"light.a"})

    assert _the_one_issue(issue_registry).dismissed_version is not None

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=1))
    await hass.async_block_till_done()
    assert hass_storage[STORAGE_KEY]["data"] == {
        "mock_repair": {"script.haunted": ["light.a", "light.b"]}
    }


async def test_a_change_in_the_text_is_not_taking_it_back(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test rewriting an issue's text leaves what was ignored alone.

    Home Assistant calls a renamed dashboard in an issue's text an "update",
    the same word it uses for somebody taking their ignore back.
    """
    await _set_up(hass)
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a"})
    await _ignore_what_is_up(hass, issue_registry)
    await _look(repair, {"light.a", "light.b"})

    repair.name = "Renamed"
    await _look(repair, {"light.a", "light.b"})
    await _look(repair, {"light.a"})

    assert _the_one_issue(issue_registry).dismissed_version is not None


async def test_taking_it_back_right_after_a_start_counts(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test un-ignoring before Spook has looked again is not undone.

    In the minutes after a start an issue can be up from before, with Spook
    not yet having said what it is about. Taking the ignore back then is
    still somebody's choice, and the next look should not overrule it.
    """
    unload = await _set_up(hass)
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a"})
    await _ignore_what_is_up(hass, issue_registry)

    unload()
    hass.data.pop(DATA_DISMISSALS)
    await _set_up(hass)
    ir.async_ignore_issue(
        hass, DOMAIN, _the_one_issue(issue_registry).issue_id, ignore=False
    )

    await _look(HauntedScriptRepair(hass), {"light.a"})

    assert _the_one_issue(issue_registry).dismissed_version is None


async def test_taking_the_ignore_back_is_heard(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test un-ignoring an issue makes its findings news again.

    An issue Spook ignores on its own stays where Home Assistant lists the
    ignored ones, so there is still a way back from that decision.
    """
    await _set_up(hass)
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a", "light.b"})
    await _ignore_what_is_up(hass, issue_registry)
    await _look(repair, {"light.a"})

    ir.async_ignore_issue(
        hass, DOMAIN, _the_one_issue(issue_registry).issue_id, ignore=False
    )
    await _look(repair, {"light.a"})

    assert _the_one_issue(issue_registry).dismissed_version is None


async def test_an_ignore_from_before_is_kept(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an issue ignored before Spook wrote these down is not forgotten.

    Somebody who pressed ignore on an earlier version has that only on the
    issue itself, and should not have to press it again.
    """
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a", "light.b"})
    await _ignore_what_is_up(hass, issue_registry)

    # Spook updated: dismissals arrive, and know nothing yet.
    await _set_up(hass)
    await _look(repair, {"light.a", "light.b"})
    await _look(repair, {"light.a"})

    assert _the_one_issue(issue_registry).dismissed_version is not None


async def test_ignoring_an_issue_that_just_went_still_counts(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test choosing ignore after the issue was cleared does not crash.

    The menu stays open while the findings move underneath it, and Home
    Assistant raises on ignoring an issue that is not there. The choice was
    still made, and holds when the issue comes back.
    """
    await _set_up(hass)
    repair = HauntedScriptRepair(hass)
    await _look(repair, {"light.a"})

    flow = _RemoveOrIgnoreFixFlow()
    flow.hass = hass
    flow.issue_id = _the_one_issue(issue_registry).issue_id

    await _look(repair, set())
    result = await flow.async_step_ignore()
    assert result["type"] == "abort"

    await _look(repair, {"light.a"})

    assert _the_one_issue(issue_registry).dismissed_version is not None


async def test_statistics_kept_the_old_way_are_carried_over(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test statistics kept in the old store of their own are still kept.

    That store held them after the issue was gone, so nothing else knows.
    """
    hass_storage["spook.kept_statistics"] = {
        "version": 1,
        "minor_version": 1,
        "key": "spook.kept_statistics",
        "data": {"statistic_ids": ["sensor.ghost", "sensor.gone"]},
    }

    await _set_up(hass)

    assert hass.data[DATA_DISMISSALS].async_dismissed(
        "orphaned_statistics", "orphaned_statistics"
    ) == {"sensor.ghost", "sensor.gone"}
    assert hass_storage[STORAGE_KEY]["data"] == {
        "orphaned_statistics": {"orphaned_statistics": ["sensor.ghost", "sensor.gone"]}
    }
    assert "spook.kept_statistics" not in hass_storage
