"""Tests for device references through the device functions in templates."""

# pylint: disable=wrong-import-order,protected-access
# ruff: noqa: SLF001
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.ectoplasms.automation.repairs.unknown_device_references import (
    SpookRepair as AutomationSpookRepair,
)
from custom_components.spook.ectoplasms.script.repairs.unknown_device_references import (
    SpookRepair as ScriptSpookRepair,
)
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr

# Written out as the registry would hand them over, a `uuid4().hex`. A
# placeholder like `ghost_device` is not shaped like a device ID and is
# skipped before it can be reported, which is the point of that check.
_KNOWN_DEVICE = "1d2fc0cc8c2d37b91a80aba97ed69adc"
_GHOST_DEVICE = "052b668647129b431b1f10448e96e8ec"

_RAW_CONFIG = {
    "actions": [
        {
            "action": "light.turn_on",
            "target": {"entity_id": f"{{{{ device_entities('{_GHOST_DEVICE}') }}}}"},
        },
    ],
}


@pytest.mark.parametrize(
    ("repair_class", "entity_kwargs"),
    [
        pytest.param(
            AutomationSpookRepair,
            {"referenced_devices": set()},
            id="automation",
        ),
        pytest.param(
            ScriptSpookRepair,
            {"script": SimpleNamespace(referenced_devices=set())},
            id="script",
        ),
    ],
)
async def test_template_device_entities_reference_is_detected(
    hass: HomeAssistant,
    repair_class: type,
    entity_kwargs: dict[str, Any],
) -> None:
    """Test a stale device_entities() device ID in a template is reported."""
    repair = repair_class(hass)
    repair._known_device_ids = {_KNOWN_DEVICE}

    entity = SimpleNamespace(raw_config=_RAW_CONFIG, **entity_kwargs)

    assert await repair._async_compute_unknown_references(entity) == {_GHOST_DEVICE}


async def _unknown_devices(hass: HomeAssistant, domain: str, template: str) -> set[str]:
    """Set up a real automation or script using a template, and ask the repair."""
    sequence = [
        {
            "action": "persistent_notification.create",
            "data": {"message": template},
        }
    ]
    if domain == "automation":
        config = {
            "automation": {
                "id": "lookup",
                "alias": "lookup",
                "triggers": [{"trigger": "event", "event_type": "go"}],
                "actions": sequence,
            }
        }
    else:
        config = {"script": {"lookup": {"sequence": sequence}}}

    assert await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()

    repair_class = (
        AutomationSpookRepair if domain == "automation" else ScriptSpookRepair
    )
    repair = repair_class(hass)
    await repair._async_setup_inspection()
    return await repair._async_compute_unknown_references(
        hass.data[domain].get_entity(f"{domain}.lookup")
    )


@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize(
    "template",
    [
        f"{{{{ device_attr('{_GHOST_DEVICE}', 'name_by_user') }}}}",
        f"{{{{ is_device_attr('{_GHOST_DEVICE}', 'manufacturer', 'IKEA') }}}}",
        f'{{{{ device_name("{_GHOST_DEVICE}") }}}}',
        f"{{{{ '{_GHOST_DEVICE}' | device_attr('model') }}}}",
        f"{{{{ '{_GHOST_DEVICE}' | device_name }}}}",
        f"{{{{ '{_GHOST_DEVICE}' is is_device_attr('model', 'x') }}}}",
    ],
)
async def test_device_lookup_with_a_device_id_is_detected(
    hass: HomeAssistant, domain: str, template: str
) -> None:
    """A removed device ID handed to a device lookup function is reported."""
    assert await _unknown_devices(hass, domain, template) == {_GHOST_DEVICE}


@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize(
    "template",
    [
        # An entity ID is an entity reference, not a device.
        "{{ device_attr('light.kitchen', 'name') }}",
        "{{ 'light.kitchen' | device_name }}",
        # Not shaped like a registry ID, so the lookup turns it into nothing.
        "{{ device_attr('Kitchen lamp', 'name') }}",
        "{{ is_device_attr('052B668647129B431B1F10448E96E8EC', 'model', 'x') }}",
        # A device that exists is fine.
        "{{ device_attr('KNOWN', 'name') }}",
        # Some other function that happens to end in the same name.
        f"{{{{ my_device_attr('{_GHOST_DEVICE}', 'name') }}}}",
    ],
)
async def test_device_lookup_without_an_unknown_device_id_is_not_read(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    domain: str,
    template: str,
) -> None:
    """Only a device ID that is not in the registry is reported."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    known = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "lamp")}
    )

    assert (
        await _unknown_devices(hass, domain, template.replace("KNOWN", known.id))
        == set()
    )
