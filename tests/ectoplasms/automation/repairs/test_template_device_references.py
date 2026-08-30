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
