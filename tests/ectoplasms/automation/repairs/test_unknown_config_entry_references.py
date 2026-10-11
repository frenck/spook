"""Tests for the config entries automations and scripts hand their actions."""

# pylint: disable=wrong-import-order,protected-access
# ruff: noqa: SLF001
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_SERVICE_REGISTERED
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.action_extraction import (
    ActionDescriptionsUnavailableError,
)
from custom_components.spook.draft_checking import async_check_draft
from custom_components.spook.ectoplasms.automation.repairs.unknown_config_entry_references import (
    SpookRepair as AutomationSpookRepair,
)
from custom_components.spook.ectoplasms.script.repairs.unknown_config_entry_references import (
    SpookRepair as ScriptSpookRepair,
)
import pytest
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Shaped like the IDs Home Assistant hands out, so nothing passes for the
# wrong reason. The ghost is what an entry removed and added again leaves.
_GHOST = "01JABCDEFGHJKMNPQRSTVWXYZ0"
_DUCK = "01JDUCKDNSENTRY00000000000"
_MET = "01JMETENTRY000000000000000"

_REPAIRS = {"automation": AutomationSpookRepair, "script": ScriptSpookRepair}


@pytest.fixture(name="entries")
async def _entries(hass: HomeAssistant) -> None:
    """Set up two real actions that take a config entry, and two entries.

    Duck DNS takes one of its own, with a `config_entry` selector that names
    the integration. Reloading a config entry takes any. Neither entry is
    set up: an entry that exists but is not loaded is not judged anyway.
    """
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "duckdns", {})
    MockConfigEntry(domain="duckdns", entry_id=_DUCK, title="Duck").add_to_hass(hass)
    MockConfigEntry(domain="met", entry_id=_MET, title="Home").add_to_hass(hass)
    await hass.async_block_till_done()


def _set_txt(entry_id: Any, **step: Any) -> dict[str, Any]:
    """Return a step that sets a Duck DNS TXT record through this entry."""
    return {
        "action": "duckdns.set_txt",
        "data": {"config_entry_id": entry_id, "txt": "boo"},
        **step,
    }


async def _async_set_up(
    hass: HomeAssistant,
    domain: str,
    sequence: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> None:
    """Set up a real automation or script running these steps."""
    if domain == "automation":
        config = {
            "automation": {
                "id": "lookup",
                "alias": "Lookup",
                "triggers": [{"trigger": "event", "event_type": "go"}],
                "actions": sequence,
                **(extra or {}),
            }
        }
    else:
        config = {
            "script": {
                "lookup": {"alias": "Lookup", "sequence": sequence, **(extra or {})}
            }
        }

    assert await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()


async def _unknown(
    hass: HomeAssistant,
    domain: str,
    sequence: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> set[str]:
    """Set up a real automation or script, and ask the repair about it."""
    await _async_set_up(hass, domain, sequence, extra)

    repair = _REPAIRS[domain](hass)
    await repair._async_setup_inspection()
    return await repair._async_compute_unknown_references(
        hass.data[domain].get_entity(f"{domain}.lookup")
    )


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_an_entry_that_does_not_exist_is_reported(
    hass: HomeAssistant, domain: str
) -> None:
    """Home Assistant refuses an entry it does not have, once the step runs."""
    await _async_set_up(hass, domain, [_set_txt(_GHOST)])

    repair = _REPAIRS[domain](hass)
    await repair.async_inspect()

    issue = async_issue_about(ir.async_get(hass), f"{repair.repair}_{domain}.lookup")
    assert issue is not None
    assert issue.translation_key == repair.repair
    assert issue.translation_placeholders == {
        "config_entries": f"- `{_GHOST}`",
        domain: "Lookup",
        "edit": (
            "/config/automation/edit/lookup"
            if domain == "automation"
            else "/config/script/edit/lookup"
        ),
        "entity_id": f"{domain}.lookup",
    }


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_an_entry_of_another_integration_is_reported(
    hass: HomeAssistant, domain: str
) -> None:
    """The selector names the integration, so another one's entry is wrong.

    Home Assistant refuses that too, with `service_config_entry_wrong_domain`.
    The issue says whose entry it is, which is usually where it came from.
    """
    await _async_set_up(hass, domain, [_set_txt(_MET)])

    repair = _REPAIRS[domain](hass)
    await repair.async_inspect()

    issue = async_issue_about(ir.async_get(hass), f"{repair.repair}_{domain}.lookup")
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["config_entries"] == (
        f"- `{_MET}` (belongs to Home, of `met`)"
    )


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_an_entry_of_the_integration_is_left_alone(
    hass: HomeAssistant, domain: str
) -> None:
    """The entry exists, and is of the integration the action asks for."""
    assert await _unknown(hass, domain, [_set_txt(_DUCK)]) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_an_entry_of_any_integration_goes_where_no_integration_is_named(
    hass: HomeAssistant, domain: str
) -> None:
    """Reloading a config entry takes any entry, as long as it exists."""
    sequence = [
        {"action": "homeassistant.reload_config_entry", "data": {"entry_id": _MET}},
        {"action": "homeassistant.reload_config_entry", "data": {"entry_id": _GHOST}},
    ]

    assert await _unknown(hass, domain, sequence) == {_GHOST}


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize(
    "entry_id",
    [
        pytest.param("{{ states('input_text.duck_entry') }}", id="template"),
        pytest.param("", id="empty"),
    ],
)
async def test_what_is_only_known_when_it_runs_is_left_alone(
    hass: HomeAssistant, domain: str, entry_id: str
) -> None:
    """A template is whatever it renders to, and empty picks the only entry."""
    assert await _unknown(hass, domain, [_set_txt(entry_id)]) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_data_that_is_a_template_as_a_whole_is_left_alone(
    hass: HomeAssistant, domain: str
) -> None:
    """Data rendered from one template is only known when it runs."""
    step = {
        "action": "duckdns.set_txt",
        "data": f"{{{{ {{'config_entry_id': '{_GHOST}'}} }}}}",
    }

    assert await _unknown(hass, domain, [step]) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_data_under_a_data_template_is_left_alone(
    hass: HomeAssistant, domain: str
) -> None:
    """A `data_template` rendered as a whole can replace what `data` holds."""
    step = {
        "action": "duckdns.set_txt",
        "data": {"config_entry_id": _GHOST},
        "data_template": f"{{{{ {{'config_entry_id': '{_DUCK}'}} }}}}",
    }

    assert await _unknown(hass, domain, [step]) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_data_template_goes_over_data(hass: HomeAssistant, domain: str) -> None:
    """Home Assistant merges `data_template` over `data`, so that one is used."""
    step = {
        "action": "duckdns.set_txt",
        "data": {"config_entry_id": _DUCK},
        "data_template": {"config_entry_id": _GHOST},
    }

    assert await _unknown(hass, domain, [step]) == {_GHOST}


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_a_disabled_step_is_left_alone(hass: HomeAssistant, domain: str) -> None:
    """A parked step runs nothing, but a running one with the same entry does."""
    parked = [_set_txt(_GHOST, enabled=False)]
    assert await _unknown(hass, domain, parked) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_a_disabled_step_does_not_hide_a_running_one(
    hass: HomeAssistant, domain: str
) -> None:
    """The same entry in a step that runs is still reported."""
    sequence = [_set_txt(_GHOST, enabled=False), {"if": [], "then": [_set_txt(_GHOST)]}]

    assert await _unknown(hass, domain, sequence) == {_GHOST}


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_only_fields_with_a_config_entry_selector_are_read(
    hass: HomeAssistant, domain: str
) -> None:
    """Duck DNS's TXT record is text, whatever it holds."""
    step = {
        "action": "duckdns.set_txt",
        "data": {"config_entry_id": _DUCK, "txt": _GHOST},
    }

    assert await _unknown(hass, domain, [step]) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_a_field_name_alone_says_nothing(
    hass: HomeAssistant, domain: str
) -> None:
    """An action that does not describe a field as a config entry is not judged.

    Not even when the field is called `config_entry_id`: an action is free to
    mean something else by it.
    """
    hass.services.async_register("haunted", "boo", lambda _call: None)
    async_set_service_schema(
        hass,
        "haunted",
        "boo",
        {"fields": {"config_entry_id": {"selector": {"text": {}}}}},
    )
    hass.services.async_register("haunted", "undescribed", lambda _call: None)
    sequence = [
        {"action": "haunted.boo", "data": {"config_entry_id": _GHOST}},
        {"action": "haunted.undescribed", "data": {"config_entry_id": _GHOST}},
    ]

    assert await _unknown(hass, domain, sequence) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_an_action_that_is_not_there_is_not_judged(
    hass: HomeAssistant, domain: str
) -> None:
    """Without its integration loaded, an action says nothing about itself."""
    step = {
        "action": "nordpool.get_prices_for_date",
        "data": {"config_entry": _GHOST},
    }

    assert await _unknown(hass, domain, [step]) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_a_field_in_a_section_is_read(hass: HomeAssistant, domain: str) -> None:
    """A section only groups fields in the editor; they go into the data as is."""
    hass.services.async_register("haunted", "boo", lambda _call: None)
    async_set_service_schema(
        hass,
        "haunted",
        "boo",
        {
            "fields": {
                "advanced": {
                    "fields": {
                        "entry": {
                            "selector": {"config_entry": {"integration": "haunted"}}
                        }
                    }
                }
            }
        },
    )

    step = {"action": "haunted.boo", "data": {"entry": _GHOST}}
    assert await _unknown(hass, domain, [step]) == {_GHOST}


@pytest.mark.usefixtures("entries")
async def test_a_script_field_takes_whatever_it_is_handed(hass: HomeAssistant) -> None:
    """A script's selector only tells the editor what to offer."""
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "pick": {
                    "fields": {
                        "entry": {
                            "selector": {"config_entry": {"integration": "duckdns"}}
                        }
                    },
                    "sequence": [],
                }
            }
        },
    )
    await hass.async_block_till_done()

    step = {"action": "script.pick", "data": {"entry": _GHOST}}
    assert await _unknown(hass, "automation", [step]) == set()


@pytest.mark.usefixtures("entries")
async def test_what_a_script_field_shows_is_never_run(hass: HomeAssistant) -> None:
    """The example of a field is shown in the editor, not run."""
    fields = {"step": {"example": _set_txt(_GHOST), "selector": {"object": {}}}}

    assert await _unknown(hass, "script", [], {"fields": fields}) == set()


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize("key", ["variables", "data"])
async def test_an_action_shaped_value_is_no_action(
    hass: HomeAssistant, domain: str, key: str
) -> None:
    """Below a key that holds values, nothing is an action, whatever its shape."""
    holder: dict[str, Any] = {key: {"later": _set_txt(_GHOST)}}
    if key == "data":
        holder = {"action": "homeassistant.reload_config_entry", **holder}

    assert await _unknown(hass, domain, [holder]) == set()


@pytest.mark.usefixtures("entries")
async def test_the_issue_goes_once_the_entry_exists(hass: HomeAssistant) -> None:
    """Added again under the same ID, nothing is wrong any more."""
    await _async_set_up(hass, "automation", [_set_txt(_GHOST)])
    repair = AutomationSpookRepair(hass)
    issue_id = f"{repair.repair}_automation.lookup"

    await repair._async_inspect_with_cleanup()
    assert async_issue_about(ir.async_get(hass), issue_id) is not None

    MockConfigEntry(domain="duckdns", entry_id=_GHOST).add_to_hass(hass)
    await repair._async_inspect_with_cleanup()
    assert async_issue_about(ir.async_get(hass), issue_id) is None


@pytest.mark.usefixtures("entries")
async def test_an_issue_stays_when_the_actions_cannot_be_read(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not knowing what the actions take is no reason to drop an issue."""
    await _async_set_up(hass, "automation", [_set_txt(_GHOST)])
    repair = AutomationSpookRepair(hass)
    issue_id = f"{repair.repair}_automation.lookup"

    await repair._async_inspect_with_cleanup()
    assert async_issue_about(ir.async_get(hass), issue_id) is not None

    async def _broken(_hass: HomeAssistant) -> dict[str, Any]:
        message = "No module named 'hassil'"
        raise ModuleNotFoundError(message)

    monkeypatch.setattr(
        "custom_components.spook.action_extraction.async_get_all_descriptions",
        _broken,
    )
    with pytest.raises(ActionDescriptionsUnavailableError):
        await repair._async_inspect_with_cleanup()
    assert async_issue_about(ir.async_get(hass), issue_id) is not None


@pytest.mark.parametrize("repair_class", [AutomationSpookRepair, ScriptSpookRepair])
def test_looks_again_when_entries_or_actions_change(repair_class: type) -> None:
    """An entry added or removed, or an action showing up, changes the answer."""
    assert repair_class.inspect_config_entry_changed is True
    assert repair_class.inspect_on_reload is True
    assert EVENT_SERVICE_REGISTERED in repair_class.inspect_events


@pytest.mark.usefixtures("entries")
@pytest.mark.parametrize("domain", ["automation", "script"])
async def test_a_draft_is_checked_the_same_way(
    hass: HomeAssistant, domain: str
) -> None:
    """A draft gets told before it is saved, by the same repair."""
    steps = [_set_txt(_GHOST), _set_txt(_DUCK), _set_txt(_MET, enabled=False)]
    draft: dict[str, Any] = (
        {"triggers": [], "actions": steps}
        if domain == "automation"
        else {"sequence": steps}
    )

    found = await async_check_draft(hass, domain, draft)

    assert found == {"config_entries": [_GHOST]}


@pytest.mark.usefixtures("entries")
async def test_actions_that_cannot_describe_themselves_cost_this_check_only(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reading every services.yaml can fail, and the rest of a draft is read."""

    async def _broken(_hass: HomeAssistant) -> dict[str, Any]:
        message = "No module named 'hassil'"
        raise ModuleNotFoundError(message)

    monkeypatch.setattr(
        "custom_components.spook.action_extraction.async_get_all_descriptions",
        _broken,
    )
    draft = {"sequence": [_set_txt(_GHOST), {"action": "light.xboo"}]}

    assert await async_check_draft(hass, "script", draft) == {
        "services": ["light.xboo"]
    }
