"""Tests for device references via device_entities() in templates."""

# pylint: disable=wrong-import-order,protected-access
# ruff: noqa: SLF001
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from custom_components.spook.ectoplasms.automation.repairs.unknown_device_references import (
    SpookRepair as AutomationSpookRepair,
)
from custom_components.spook.ectoplasms.script.repairs.unknown_device_references import (
    SpookRepair as ScriptSpookRepair,
)
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_RAW_CONFIG = {
    "actions": [
        {
            "action": "light.turn_on",
            "target": {"entity_id": "{{ device_entities('ghost_device') }}"},
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
    repair._known_device_ids = {"known_device"}

    entity = SimpleNamespace(raw_config=_RAW_CONFIG, **entity_kwargs)

    assert await repair._async_compute_unknown_references(entity) == {"ghost_device"}
