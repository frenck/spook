"""Smoke tests for the table-driven unknown helper source repair.

Each test sets up a real helper integration with a nonexistent source
entity and runs the repair against it, so a change to a helper's config
entry option shape fails here instead of at the user's place.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.repairs.unknown_helper_source_references import (
    SpookRepair,
)
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

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"unknown_helper_source_references_{entry.entry_id}",
    )
    assert issue, f"No issue was created for the {helper_domain} ghost source"
    assert issue.translation_placeholders
    assert issue.translation_placeholders["domain"] == helper_domain
