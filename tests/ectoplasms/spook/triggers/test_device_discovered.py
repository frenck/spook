"""Tests for the spook.device_discovered trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_ZEROCONF
from homeassistant.core import CoreState
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
import pytest

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import HomeAssistant

_DOMAIN = "gadget"


class _GadgetFlow(config_entries.ConfigFlow):
    """A config flow that finds gadgets, and waits to be confirmed."""

    VERSION = 1

    async def _async_found(self, data: dict[str, Any]) -> Any:
        """Note the gadget, and wait on the discovered list for somebody."""
        await self.async_set_unique_id(data["serial"])
        self.context["title_placeholders"] = {"name": data["name"]}
        return self.async_show_form(step_id="confirm")

    async def async_step_zeroconf(self, discovery_info: dict[str, Any]) -> Any:
        """Handle a gadget found on the network."""
        return await self._async_found(discovery_info)

    async def async_step_import(self, import_data: dict[str, Any]) -> Any:
        """Handle a gadget moved over from YAML."""
        return await self._async_found(import_data)

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> Any:
        """Wait for somebody to set the gadget up."""
        del user_input
        return self.async_show_form(step_id="confirm")


@pytest.fixture(autouse=True)
def _gadget(hass: HomeAssistant) -> Iterator[None]:
    """Provide an integration that discovers gadgets."""
    mock_integration(hass, MockModule(_DOMAIN))
    mock_platform(hass, f"{_DOMAIN}.config_flow", None)
    with mock_config_flow(_DOMAIN, _GadgetFlow):
        yield


async def _find(
    hass: HomeAssistant,
    serial: str = "AB12",
    name: str = "Desk gadget",
    source: str = SOURCE_ZEROCONF,
) -> str:
    """Have Home Assistant find a gadget, and return the discovery."""
    result = await hass.config_entries.flow.async_init(
        _DOMAIN, context={"source": source}, data={"serial": serial, "name": name}
    )
    await hass.async_block_till_done()
    return result["flow_id"]


async def _automation(hass: HomeAssistant) -> list[dict]:
    """Set up an automation on the trigger and record every run."""
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
                    "alias": "something new",
                    "trigger": {"platform": "spook.device_discovered"},
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "flow_id": "{{ trigger.flow_id }}",
                                "domain": "{{ trigger.domain }}",
                                "source": "{{ trigger.source }}",
                                "name": "{{ trigger.name }}",
                                "unique_id": "{{ trigger.unique_id }}",
                                "title_placeholders": (
                                    "{{ trigger.title_placeholders }}"
                                ),
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def test_a_new_discovery_is_reported(hass: HomeAssistant) -> None:
    """Test something found fires the trigger, with what and how."""
    ran = await _automation(hass)

    flow_id = await _find(hass)

    assert ran == [
        {
            "flow_id": flow_id,
            "domain": _DOMAIN,
            "source": SOURCE_ZEROCONF,
            "name": "Desk gadget",
            "unique_id": "AB12",
            "title_placeholders": {"name": "Desk gadget"},
        }
    ]


async def test_the_same_device_found_again_is_reported_once(
    hass: HomeAssistant,
) -> None:
    """Test a device found again, under a new discovery, stays quiet."""
    ran = await _automation(hass)

    flow_id = await _find(hass)
    hass.config_entries.flow.async_abort(flow_id)
    await _find(hass)
    await _find(hass, serial="CD34", name="Other gadget")

    assert [run["unique_id"] for run in ran] == ["AB12", "CD34"]


async def test_what_was_already_on_the_list_is_not_news(
    hass: HomeAssistant,
) -> None:
    """Test discoveries made before the automation loaded are left alone."""
    flow_id = await _find(hass)
    ran = await _automation(hass)

    hass.config_entries.flow.async_abort(flow_id)
    await _find(hass)

    assert ran == []


async def test_what_is_found_while_starting_is_noted_not_reported(
    hass: HomeAssistant,
) -> None:
    """Test devices found again during a restart are no news, then or later.

    Home Assistant finds everything that was there before the restart while
    it starts. One of those found again once it is up is still not new.
    """
    ran = await _automation(hass)
    hass.set_state(CoreState.starting)

    flow_id = await _find(hass)
    hass.set_state(CoreState.running)
    hass.config_entries.flow.async_abort(flow_id)
    await _find(hass)

    assert ran == []


async def test_a_configuration_moved_from_yaml_is_not_a_discovery(
    hass: HomeAssistant,
) -> None:
    """Test an import, a YAML configuration moving over, does not fire."""
    ran = await _automation(hass)

    await _find(hass, source=SOURCE_IMPORT)

    assert ran == []
