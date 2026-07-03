"""Smoke tests for the unknown source entity repairs.

These repairs read private attributes of helper entities provided by
Home Assistant core (like ``_sensor_source_id``). Each test sets up the
real helper integration with a nonexistent source entity and runs the
repair against it, so a core rename of those private attributes fails
here instead of at the user's place.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.const import DOMAIN
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


@pytest.mark.parametrize(
    ("helper_domain", "options"),
    [
        pytest.param(
            "integration",
            {
                "name": "Ghostly integral",
                "source": "sensor.ghost",
                "method": "trapezoidal",
                "round": 1.0,
                "unit_prefix": "k",
                "unit_time": "h",
            },
            id="integration",
        ),
        pytest.param(
            "utility_meter",
            {
                "name": "Ghostly meter",
                "source": "sensor.ghost",
                "cycle": "monthly",
                "offset": 0,
                "net_consumption": False,
                "delta_values": False,
                "periodically_resetting": True,
                "always_available": False,
                "tariffs": [],
            },
            id="utility_meter",
        ),
        pytest.param(
            "trend",
            {
                "name": "Ghostly trend",
                "entity_id": "sensor.ghost",
                "invert": False,
            },
            id="trend",
        ),
        pytest.param(
            "switch_as_x",
            {
                "entity_id": "switch.ghost",
                "target_domain": "light",
                "invert": False,
            },
            id="switch_as_x",
        ),
    ],
)
async def test_unknown_source_repair_smoke(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    helper_domain: str,
    options: dict[str, Any],
) -> None:
    """Test the repair detects a helper wrapping a nonexistent source."""
    entry = MockConfigEntry(
        domain=helper_domain,
        title=str(options.get("name", "Ghostly")),
        options=options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    repair_module = importlib.import_module(
        f"custom_components.spook.ectoplasms.{helper_domain}.repairs.unknown_source",
    )
    repair = repair_module.SpookRepair(hass)
    await repair.async_inspect()

    prefix = f"{repair.repair}_"
    assert any(
        issue_domain == DOMAIN and issue_id.startswith(prefix)
        for issue_domain, issue_id in issue_registry.issues
    ), f"No {repair.repair} issue was created for the ghost source"
