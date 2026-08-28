"""Tests for the repair issue triggers and condition."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.condition import ConditionConfig
from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.condition import async_get_conditions
from custom_components.spook.ectoplasms.spook.conditions.repair_issue_present import (
    SpookCondition,
)
from custom_components.spook.ectoplasms.spook.triggers.repair_issue_created import (
    SpookTrigger as CreatedTrigger,
)
from custom_components.spook.ectoplasms.spook.triggers.repair_issue_removed import (
    SpookTrigger as RemovedTrigger,
)
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the platforms.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _raise(
    hass: HomeAssistant,
    domain: str = "demo",
    issue_id: str = "boiler",
    severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
) -> None:
    """Report a repair issue, the way an integration would."""
    ir.async_create_issue(
        hass,
        domain,
        issue_id,
        is_fixable=False,
        severity=severity,
        translation_key=issue_id,
    )


async def _condition(hass: HomeAssistant, **options: list[str]) -> SpookCondition:
    """Build the condition and set it up, the way core would."""
    condition = SpookCondition(hass, ConditionConfig(options=options))
    await condition.async_setup()
    return condition


async def _automation(hass: HomeAssistant, triggers: list[dict]) -> list[dict]:
    """Set up an automation on the given triggers and record every run."""
    ran: list[dict] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(dict(call.data))

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "repairs",
                    "trigger": triggers,
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "domain": "{{ trigger.domain }}",
                                "issue_id": "{{ trigger.issue_id }}",
                                "severity": "{{ trigger.severity | default('none') }}",
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def test_both_triggers_are_discovered(hass: HomeAssistant) -> None:
    """The triggers turn up in Spook's discovery, under plain keys."""
    triggers = await async_get_triggers(hass)
    assert "repair_issue_created" in triggers
    assert "repair_issue_removed" in triggers


async def test_the_condition_is_discovered(hass: HomeAssistant) -> None:
    """The condition turns up in Spook's discovery too."""
    assert "repair_issue_present" in await async_get_conditions(hass)


@pytest.mark.parametrize(
    "trigger_class", [CreatedTrigger, RemovedTrigger, SpookCondition]
)
async def test_no_options_is_fine(hass: HomeAssistant, trigger_class) -> None:  # noqa: ANN001
    """Asking about every issue there is needs no options."""
    assert await trigger_class.async_validate_config(hass, {}) == {"options": {}}


@pytest.mark.parametrize("provider", [CreatedTrigger, SpookCondition])
async def test_a_made_up_severity_is_refused(hass: HomeAssistant, provider) -> None:  # noqa: ANN001
    """Severity only takes the three Home Assistant has."""
    with pytest.raises(vol.Invalid):
        await provider.async_validate_config(
            hass, {"options": {"severity": ["catastrophic"]}}
        )


async def test_it_fires_when_an_issue_turns_up(hass: HomeAssistant) -> None:
    """A new issue sets the trigger off, carrying what it is."""
    ran = await _automation(hass, [{"platform": "spook.repair_issue_created"}])

    _raise(hass, severity=ir.IssueSeverity.ERROR)
    await hass.async_block_till_done()

    assert ran == [{"domain": "demo", "issue_id": "boiler", "severity": "error"}]


async def test_reporting_the_same_issue_again_does_not_fire(
    hass: HomeAssistant,
) -> None:
    """A repair checked on a schedule would otherwise fire on every pass.

    The registry treats a repeat as an update rather than a creation, which is
    what makes this safe, so it is worth pinning.
    """
    ran = await _automation(hass, [{"platform": "spook.repair_issue_created"}])

    _raise(hass)
    await hass.async_block_till_done()
    assert len(ran) == 1

    for _ in range(3):
        _raise(hass)
        await hass.async_block_till_done()

    assert len(ran) == 1, "fired again for an issue that was already there"


async def test_ignoring_an_issue_does_not_fire(hass: HomeAssistant) -> None:
    """Telling Home Assistant to stop nagging is not a new issue."""
    ran = await _automation(hass, [{"platform": "spook.repair_issue_created"}])

    _raise(hass)
    await hass.async_block_till_done()
    assert len(ran) == 1

    ir.async_ignore_issue(hass, "demo", "boiler", ignore=True)
    await hass.async_block_till_done()

    assert len(ran) == 1


async def test_it_fires_when_an_issue_goes_away(hass: HomeAssistant) -> None:
    """Removal sets the other trigger off."""
    _raise(hass)
    await hass.async_block_till_done()

    ran = await _automation(hass, [{"platform": "spook.repair_issue_removed"}])

    ir.async_delete_issue(hass, "demo", "boiler")
    await hass.async_block_till_done()

    assert ran == [{"domain": "demo", "issue_id": "boiler", "severity": "none"}]


async def test_the_removed_trigger_stays_quiet_for_anything_else(
    hass: HomeAssistant,
) -> None:
    """The registry announces creations and updates on the same event.

    Without checking which it was, this would fire the moment an issue turned
    up, which is the opposite of what it says on the tin.
    """
    ran = await _automation(hass, [{"platform": "spook.repair_issue_removed"}])

    _raise(hass)
    await hass.async_block_till_done()
    assert not ran, "fired when an issue was created"

    _raise(hass, severity=ir.IssueSeverity.CRITICAL)
    await hass.async_block_till_done()
    assert not ran, "fired when an issue was updated"

    ir.async_ignore_issue(hass, "demo", "boiler", ignore=True)
    await hass.async_block_till_done()
    assert not ran, "fired when an issue was ignored"

    ir.async_delete_issue(hass, "demo", "boiler")
    await hass.async_block_till_done()
    assert len(ran) == 1, "did not fire when the issue actually went away"


async def test_the_removed_trigger_honours_the_domain_filter(
    hass: HomeAssistant,
) -> None:
    """Naming integrations limits the removals it reports, too."""
    _raise(hass, domain="zwave_js", issue_id="node_dead")
    _raise(hass, domain="hue", issue_id="bridge_gone")
    await hass.async_block_till_done()

    ran = await _automation(
        hass,
        [{"platform": "spook.repair_issue_removed", "options": {"domain": ["hue"]}}],
    )

    ir.async_delete_issue(hass, "zwave_js", "node_dead")
    ir.async_delete_issue(hass, "hue", "bridge_gone")
    await hass.async_block_till_done()

    assert [run["domain"] for run in ran] == ["hue"]


async def test_the_domain_filter_turns_the_others_down(hass: HomeAssistant) -> None:
    """Naming integrations limits it to those."""
    ran = await _automation(
        hass,
        [{"platform": "spook.repair_issue_created", "options": {"domain": ["hue"]}}],
    )

    _raise(hass, domain="zwave_js", issue_id="node_dead")
    _raise(hass, domain="hue", issue_id="bridge_gone")
    await hass.async_block_till_done()

    assert [run["domain"] for run in ran] == ["hue"]


async def test_the_severity_filter_turns_the_others_down(hass: HomeAssistant) -> None:
    """Naming severities limits it to those."""
    ran = await _automation(
        hass,
        [
            {
                "platform": "spook.repair_issue_created",
                "options": {"severity": ["critical"]},
            }
        ],
    )

    _raise(hass, issue_id="mild", severity=ir.IssueSeverity.WARNING)
    _raise(hass, issue_id="dire", severity=ir.IssueSeverity.CRITICAL)
    await hass.async_block_till_done()

    assert [run["issue_id"] for run in ran] == ["dire"]


async def test_the_condition_passes_while_something_is_outstanding(
    hass: HomeAssistant,
) -> None:
    """Present means present, and gone means gone."""
    condition = await _condition(hass)

    assert condition.async_check() is False

    _raise(hass)
    await hass.async_block_till_done()
    assert condition.async_check() is True

    ir.async_delete_issue(hass, "demo", "boiler")
    await hass.async_block_till_done()
    assert condition.async_check() is False


async def test_the_condition_ignores_ignored_issues(hass: HomeAssistant) -> None:
    """Ignoring one is telling Home Assistant to stop bringing it up.

    Overruling that here would make the condition useless for the thing it is
    for: holding something back until the house is in order.
    """
    condition = await _condition(hass)

    _raise(hass)
    await hass.async_block_till_done()
    assert condition.async_check() is True

    ir.async_ignore_issue(hass, "demo", "boiler", ignore=True)
    await hass.async_block_till_done()

    assert condition.async_check() is False, "counted an issue somebody had ignored"


async def test_the_condition_ignores_an_issue_waiting_to_be_confirmed(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """An issue restored from before a restart is not known to be real yet.

    Home Assistant keeps non-persistent issues across a restart so it can
    remember whether they were ignored, but marks them inactive until the
    integration reports them again. Counting those would make this pass every
    startup for anything that has since been fixed.
    """
    hass_storage[ir.STORAGE_KEY] = {
        "version": ir.STORAGE_VERSION_MAJOR,
        "minor_version": ir.STORAGE_VERSION_MINOR,
        "data": {
            "issues": [
                {
                    "created": "2026-08-01T12:00:00+00:00",
                    "dismissed_version": None,
                    "domain": "demo",
                    "is_persistent": False,
                    "issue_id": "boiler",
                }
            ]
        },
    }
    await ir.async_load(hass)

    restored = ir.async_get(hass).async_get_issue("demo", "boiler")
    assert restored is not None
    assert restored.active is False, "expected a restored issue to await confirmation"

    condition = await _condition(hass)
    assert condition.async_check() is False, "counted an unconfirmed issue"

    # And once the integration reports it again, it counts.
    _raise(hass)
    await hass.async_block_till_done()
    assert condition.async_check() is True


async def test_the_condition_filters_the_same_way(hass: HomeAssistant) -> None:
    """The filters read the same on the condition as on the trigger."""
    condition = await _condition(hass, domain=["hue"], severity=["critical"])

    _raise(hass, domain="zwave_js", issue_id="node", severity=ir.IssueSeverity.CRITICAL)
    _raise(hass, domain="hue", issue_id="mild", severity=ir.IssueSeverity.WARNING)
    await hass.async_block_till_done()
    assert condition.async_check() is False, "matched on only half the filter"

    _raise(hass, domain="hue", issue_id="dire", severity=ir.IssueSeverity.CRITICAL)
    await hass.async_block_till_done()
    assert condition.async_check() is True
