"""Tests for Spook's take on restarting Home Assistant."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from homeassistant.core import HassJob, HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from custom_components.spook.ectoplasms.homeassistant.services import restart


def _call(hass: HomeAssistant) -> ServiceCall:
    """Return a restart call that does not force it."""
    return ServiceCall(
        hass, "homeassistant", "restart", {"safe_mode": False, "force": False}
    )


async def test_a_refused_restart_is_not_reported_as_done(
    hass: HomeAssistant,
) -> None:
    """Test Home Assistant refusing to restart reaches whoever asked.

    It checks the configuration first and refuses when that is broken. The
    refusal went nowhere, so an automation asking for a restart carried on as
    if Home Assistant was on its way back up.
    """

    async def _refuses(_call: ServiceCall) -> None:
        msg = "The system cannot restart because the configuration is not valid"
        raise HomeAssistantError(msg)

    service = restart.SpookService(hass)
    service.overriden_service = SimpleNamespace(job=HassJob(_refuses))

    with pytest.raises(HomeAssistantError, match="configuration is not valid"):
        await service.async_handle_service(_call(hass))


async def test_a_restart_that_goes_ahead_is_handed_the_call(
    hass: HomeAssistant,
) -> None:
    """Test the call still reaches Home Assistant's own restart."""
    seen: list[ServiceCall] = []

    async def _restarts(call: ServiceCall) -> None:
        seen.append(call)

    service = restart.SpookService(hass)
    service.overriden_service = SimpleNamespace(job=HassJob(_restarts))
    call = _call(hass)

    await service.async_handle_service(call)

    assert seen == [call]
