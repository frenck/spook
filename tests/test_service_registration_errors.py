"""Tests for what Spook says when a service cannot be registered."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from custom_components.spook.services import (
    AbstractSpookEntityComponentService,
    AbstractSpookEntityService,
    AbstractSpookService,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall


class _EntityService(AbstractSpookEntityService):
    """A Spook entity service pointed at a platform that is not loaded."""

    domain = "sensor"
    platform = "spook"
    service = "do_something"
    schema = {}

    async def async_handle_service(self, entity: object, call: ServiceCall) -> None:
        """Do nothing; registration never gets this far in these tests."""


class _ComponentService(AbstractSpookEntityComponentService):
    """A Spook component service pointed at a component that is not loaded."""

    domain = "not_loaded"
    service = "do_something"
    schema = {}

    async def async_handle_service(self, entity: object, call: ServiceCall) -> None:
        """Do nothing; registration never gets this far in these tests."""


def test_missing_platform_says_so_in_one_sentence(hass: HomeAssistant) -> None:
    """Test the error names the platform, as a sentence rather than a tuple.

    The message is built from implicitly concatenated f-strings. A trailing
    comma in there turns the whole thing into a one-tuple, and the error then
    renders as `('Could not find platform ...',)`, parentheses and quotes
    included. It read that way until ruff 0.16 grew a check for it.
    """
    service = _EntityService(hass)

    with pytest.raises(RuntimeError) as caught:
        service.async_register()

    assert caught.value.args[0] == (
        "Could not find platform spook for domain sensor to register service:"
        " sensor.do_something"
    )
    assert str(caught.value).startswith("Could not find platform")


def test_missing_component_says_so_in_one_sentence(hass: HomeAssistant) -> None:
    """Test the error names the component, as a sentence rather than a tuple."""
    service = _ComponentService(hass)

    with pytest.raises(RuntimeError) as caught:
        service.async_register()

    assert caught.value.args[0] == (
        "Could not find entity component not_loaded to register service:"
        " not_loaded.do_something"
    )
    assert str(caught.value).startswith("Could not find entity component")


async def test_a_service_for_an_unloaded_domain_is_not_registered(
    hass: HomeAssistant,
) -> None:
    """Spook does not put an action on somebody else's domain until it is there.

    Registering it anyway would offer an action whose handler reaches for an
    integration that was never set up, and it would fail there instead of
    simply not existing.
    """

    class _Elsewhere(AbstractSpookService):
        """A service on a domain nobody has loaded."""

        domain = "not_a_loaded_integration"
        service = "do_something"

        async def async_handle_service(self, call: ServiceCall) -> None:
            """Handle the service call."""

    _Elsewhere(hass).async_register()

    assert not hass.services.has_service("not_a_loaded_integration", "do_something")
