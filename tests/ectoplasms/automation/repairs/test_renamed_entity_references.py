"""Tests for the automation renamed entity references repair and its fix."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from pathlib import Path

from homeassistant.config import AUTOMATION_CONFIG_PATH
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.automation.repairs.renamed_entity_references import (
    SpookRepair,
)
from custom_components.spook.entity_renames import async_get_entity_renames
from custom_components.spook.repairs import EntityRenameFixFlow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers import issue_registry as ir

_AUTOMATION_ID = "abc123"
_RENAMED = {
    "renamed_entity": "light.old",
    "renamed_to": "light.new",
    "rename_domain": "automation",
    "rename_config_id": _AUTOMATION_ID,
}


def _install_automation(
    hass: HomeAssistant,
    *,
    unique_id: str | None = _AUTOMATION_ID,
    referenced: set[str] | None = None,
    raw_config: dict | None = None,
) -> SimpleNamespace:
    """Install a fake automation entity component into hass."""
    automation = SimpleNamespace(
        entity_id="automation.test",
        name="Test automation",
        unique_id=unique_id,
        referenced_entities=referenced or set(),
        raw_config=raw_config,
    )
    hass.data.setdefault(DATA_INSTANCES, {})["automation"] = SimpleNamespace(
        entities=[automation]
    )
    return automation


def _journal(
    hass: HomeAssistant, old: str = "light.old", new: str = "light.new"
) -> None:
    """Record a rename the way the journal would have."""
    async_get_entity_renames(hass)[old] = new


def _write_automations(config_dir: str, content: str) -> Path:
    """Write an automations.yaml into the test config dir."""
    path = Path(config_dir) / AUTOMATION_CONFIG_PATH
    path.write_text(content, encoding="utf-8")
    return path


async def test_a_reference_to_a_renamed_entity_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An automation still pointing at the old ID gets a fixable issue."""
    _install_automation(hass, referenced={"light.old"})
    _journal(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN, "automation_renamed_entity_references_automation.test_light.old"
    )
    assert issue is not None
    assert issue.is_fixable
    assert issue.is_persistent
    assert issue.data == _RENAMED
    assert issue.translation_placeholders["old_entity_id"] == "light.old"
    assert issue.translation_placeholders["new_entity_id"] == "light.new"


async def test_a_reference_inside_a_template_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """`referenced_entities` misses Jinja; the raw config check catches it."""
    _install_automation(
        hass,
        raw_config={
            "condition": {
                "condition": "template",
                "value_template": "{{ states('light.old') == 'on' }}",
            }
        },
    )
    _journal(hass)

    await SpookRepair(hass).async_inspect()

    assert (
        issue_registry.async_get_issue(
            DOMAIN,
            "automation_renamed_entity_references_automation.test_light.old",
        )
        is not None
    )


async def test_an_unrelated_automation_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """An automation not referencing the old ID gets no issue."""
    _install_automation(hass, referenced={"light.other"})
    _journal(hass)

    await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


async def test_a_yaml_automation_gets_advice_instead_of_a_fix(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Without a unique ID there is nothing the editor could write."""
    _install_automation(hass, unique_id=None, referenced={"light.old"})
    _journal(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN, "automation_renamed_entity_references_automation.test_light.old"
    )
    assert issue is not None
    assert not issue.is_fixable


def _flow(hass: HomeAssistant) -> EntityRenameFixFlow:
    """Build the fix flow the way the repairs component wires it up."""
    flow = EntityRenameFixFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.issue_id = "automation_renamed_entity_references_automation.test_light.old"
    flow.data = dict(_RENAMED)
    return flow


async def test_the_confirm_step_asks_first(hass: HomeAssistant) -> None:
    """The flow opens with a confirm, it does not rewrite on its own."""
    result = await _flow(hass).async_step_init()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"


async def test_confirming_rewrites_the_automation_and_reloads(
    hass: HomeAssistant,
    hass_config_dir: str,
) -> None:
    """Submitting rewrites automations.yaml, reloads and is done."""
    automation = _install_automation(
        hass,
        referenced={"light.old"},
        raw_config={"trigger": {"entity_id": "light.old"}},
    )
    config_path = _write_automations(
        hass_config_dir,
        "- id: abc123\n"
        "  alias: Test\n"
        "  trigger:\n"
        "    - platform: state\n"
        "      entity_id: light.old\n"
        "  action: []\n",
    )

    reloads: list[ServiceCall] = []

    async def _reload(call: ServiceCall) -> None:
        """Stand in for the reload the automation component would do."""
        reloads.append(call)
        automation.referenced_entities = {"light.new"}
        automation.raw_config = {"trigger": {"entity_id": "light.new"}}

    hass.services.async_register("automation", "reload", _reload)

    result = await _flow(hass).async_step_confirm({})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert len(reloads) == 1
    rewritten = config_path.read_text(encoding="utf-8")
    assert "light.new" in rewritten
    assert "light.old" not in rewritten


async def test_a_config_that_is_not_there_cannot_be_updated(
    hass: HomeAssistant,
    hass_config_dir: str,
) -> None:
    """An automation stored elsewhere aborts with a reason to edit by hand."""
    _install_automation(hass, referenced={"light.old"})
    _write_automations(hass_config_dir, "- id: other-id\n  alias: Other\n")

    hass.services.async_register("automation", "reload", lambda _call: None)

    result = await _flow(hass).async_step_confirm({})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_update"


async def test_a_config_still_referencing_the_old_id_says_so(
    hass: HomeAssistant,
    hass_config_dir: str,
) -> None:
    """References surviving the rewrite - a blueprint's - abort differently."""
    _install_automation(hass, referenced={"light.old"}, raw_config=None)
    _write_automations(
        hass_config_dir,
        "- id: abc123\n"
        "  alias: Test\n"
        "  trigger:\n"
        "    - platform: state\n"
        "      entity_id: light.old\n",
    )

    hass.services.async_register("automation", "reload", lambda _call: None)

    result = await _flow(hass).async_step_confirm({})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "still_referenced"


async def test_a_file_with_directives_is_left_alone(
    hass: HomeAssistant,
    hass_config_dir: str,
) -> None:
    """A !include in automations.yaml must not be materialized by a rewrite."""
    _install_automation(hass, referenced={"light.old"})
    original = "- id: abc123\n  alias: !include ./alias.yaml\n"
    config_path = _write_automations(hass_config_dir, original)

    hass.services.async_register("automation", "reload", lambda _call: None)

    result = await _flow(hass).async_step_confirm({})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_update"
    assert config_path.read_text(encoding="utf-8") == original
