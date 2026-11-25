"""Tests for the script renamed entity references repair and its fix."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from pathlib import Path

from homeassistant.config import SCRIPT_CONFIG_PATH
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.entity_component import DATA_INSTANCES

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.script.repairs.renamed_entity_references import (
    SpookRepair,
)
from custom_components.spook.entity_renames import async_get_entity_renames
from custom_components.spook.repairs import EntityRenameFixFlow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers import issue_registry as ir

_SCRIPT_ID = "my_script"
_RENAMED = {
    "renamed_entity": "light.old",
    "renamed_to": "light.new",
    "rename_domain": "script",
    "rename_config_id": _SCRIPT_ID,
}


def _install_script(
    hass: HomeAssistant,
    *,
    unique_id: str | None = _SCRIPT_ID,
    referenced: set[str] | None = None,
    raw_config: dict | None = None,
) -> SimpleNamespace:
    """Install a fake script entity component into hass."""
    script = SimpleNamespace(
        entity_id="script.my_script",
        name="My script",
        unique_id=unique_id,
        referenced_entities=referenced or set(),
        raw_config=raw_config,
    )
    hass.data.setdefault(DATA_INSTANCES, {})["script"] = SimpleNamespace(
        entities=[script]
    )
    return script


def _journal(
    hass: HomeAssistant, old: str = "light.old", new: str = "light.new"
) -> None:
    """Record a rename the way the journal would have."""
    async_get_entity_renames(hass)[old] = new


def _write_scripts(config_dir: str, content: str) -> Path:
    """Write a scripts.yaml into the test config dir."""
    path = Path(config_dir) / SCRIPT_CONFIG_PATH
    path.write_text(content, encoding="utf-8")
    return path


async def test_a_reference_to_a_renamed_entity_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A script still pointing at the old ID gets a fixable issue."""
    _install_script(hass, referenced={"light.old"})
    _journal(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN, "script_renamed_entity_references_script.my_script_light.old"
    )
    assert issue is not None
    assert issue.is_fixable
    assert issue.data == _RENAMED


async def test_an_unrelated_script_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A script not referencing the old ID gets no issue."""
    _install_script(hass, referenced={"light.other"})
    _journal(hass)

    await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


async def test_a_yaml_script_gets_advice_instead_of_a_fix(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Without a unique ID there is nothing the editor could write."""
    _install_script(hass, unique_id=None, referenced={"light.old"})
    _journal(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN, "script_renamed_entity_references_script.my_script_light.old"
    )
    assert issue is not None
    assert not issue.is_fixable


def _flow(hass: HomeAssistant) -> EntityRenameFixFlow:
    """Build the fix flow the way the repairs component wires it up."""
    flow = EntityRenameFixFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.issue_id = "script_renamed_entity_references_script.my_script_light.old"
    flow.data = dict(_RENAMED)
    return flow


async def test_confirming_rewrites_the_script_and_reloads(
    hass: HomeAssistant,
    hass_config_dir: str,
) -> None:
    """Submitting rewrites scripts.yaml, reloads all scripts and is done."""
    script = _install_script(
        hass,
        referenced={"light.old"},
        raw_config={"sequence": [{"entity_id": "light.old"}]},
    )
    config_path = _write_scripts(
        hass_config_dir,
        "my_script:\n"
        "  alias: My script\n"
        "  sequence:\n"
        "    - service: light.turn_on\n"
        "      entity_id: light.old\n",
    )

    reloads: list[ServiceCall] = []

    async def _reload(call: ServiceCall) -> None:
        """Stand in for the reload the script component would do."""
        reloads.append(call)
        script.referenced_entities = {"light.new"}
        script.raw_config = {"sequence": [{"entity_id": "light.new"}]}

    hass.services.async_register("script", "reload", _reload)

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
    """A script stored elsewhere aborts with a reason to edit by hand."""
    _install_script(hass, referenced={"light.old"})
    _write_scripts(hass_config_dir, "other_script:\n  sequence: []\n")

    hass.services.async_register("script", "reload", lambda _call: None)

    result = await _flow(hass).async_step_confirm({})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_update"
