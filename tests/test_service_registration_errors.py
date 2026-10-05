"""Tests for what Spook says when a service cannot be registered."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.service import async_get_cached_service_description
from homeassistant.helpers.translation import async_get_cached_translations
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook import services
from custom_components.spook.services import (
    AbstractSpookEntityComponentService,
    AbstractSpookEntityService,
    AbstractSpookService,
    SpookServiceManager,
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


def test_a_component_that_is_not_loaded_is_not_an_error(hass: HomeAssistant) -> None:
    """Test a missing component means not yet, rather than failing.

    Home Assistant loads calendar and todo only once an integration brings
    one along, which can be after Spook or never at all. Raising here logged
    a traceback on every start for everybody without a calendar.
    """
    assert _ComponentService(hass).async_register() is False
    assert not hass.services.has_service("not_loaded", "do_something")


async def test_a_component_loaded_later_gets_its_actions(hass: HomeAssistant) -> None:
    """Test an action waits for its component, and is there once it loads.

    With its description and its translated name, the same as an action
    registered the moment Spook set up.
    """
    manager = SpookServiceManager(hass)
    await manager.async_setup()

    assert not hass.services.has_service("todo", "move_item")

    assert await async_setup_component(hass, "todo", {})
    await hass.async_block_till_done()

    assert hass.services.has_service("todo", "move_item")
    description = async_get_cached_service_description(hass, "todo", "move_item")
    assert description is not None
    assert "position" in description["fields"]
    translations = async_get_cached_translations(hass, "en", "services", "todo")
    assert translations["component.todo.services.move_item.name"] == "Move item 👻"

    manager.async_on_unload()


async def test_a_component_loaded_while_spook_sets_up_gets_its_actions(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a component that loads while Spook is still setting up counts.

    Setting up waits on the translations after the services are parked. A
    component that finishes loading right then is announced before a
    listener set up after that wait could hear it, and its actions would
    wait for good.
    """
    manager = SpookServiceManager(hass)
    inject = manager.async_inject_service_translations
    loaded = False

    async def _todo_loads_meanwhile() -> None:
        nonlocal loaded
        if not loaded:
            loaded = True
            assert await async_setup_component(hass, "todo", {})
        await inject()

    monkeypatch.setattr(
        manager, "async_inject_service_translations", _todo_loads_meanwhile
    )
    await manager.async_setup()
    await hass.async_block_till_done()

    assert hass.services.has_service("todo", "move_item")

    manager.async_on_unload()


async def test_an_injection_still_running_at_unload_writes_nothing(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test unloading stops a translation injection that is still under way.

    Injecting waits on loading translations before it writes. Left to finish
    after unload put the originals back, it would write Spook's strings again
    for an action that was just taken away.
    """
    gate = asyncio.Event()
    gate.set()
    load = services.async_get_translations

    async def _held_up(*args: Any, **kwargs: Any) -> dict[str, str]:
        await gate.wait()
        return await load(*args, **kwargs)

    monkeypatch.setattr(services, "async_get_translations", _held_up)

    manager = SpookServiceManager(hass)
    await manager.async_setup()

    gate.clear()
    assert await async_setup_component(hass, "todo", {})
    manager.async_on_unload()
    gate.set()
    await hass.async_block_till_done()

    translations = async_get_cached_translations(hass, "en", "services", "todo")
    assert "component.todo.services.move_item.name" not in translations


async def test_a_component_never_loaded_logs_nothing(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test nobody without a calendar is told to report a bug about it."""
    manager = SpookServiceManager(hass)
    await manager.async_setup()

    assert "failed to set up" not in caplog.text

    manager.async_on_unload()


async def test_a_component_loaded_after_unloading_gets_nothing(
    hass: HomeAssistant,
) -> None:
    """Test Spook stops waiting once it is unloaded itself."""
    manager = SpookServiceManager(hass)
    await manager.async_setup()
    manager.async_on_unload()

    assert await async_setup_component(hass, "todo", {})
    await hass.async_block_till_done()

    assert not hass.services.has_service("todo", "move_item")


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


async def test_a_skipped_service_gets_no_description(hass: HomeAssistant) -> None:
    """Spook does not describe an action it never registered.

    Home Assistant looks the action up while storing a description, so
    injecting one for a service that was skipped ends in a KeyError on the
    domain and takes the whole service module down with it.
    """

    class _Elsewhere(AbstractSpookService):
        """A service on a domain nobody has loaded."""

        domain = "not_a_loaded_integration"
        service = "do_something"

        async def async_handle_service(self, call: ServiceCall) -> None:
            """Handle the service call."""

    manager = SpookServiceManager(hass)
    manager._service_schemas = {  # noqa: SLF001
        "not_a_loaded_integration_do_something": {"name": "Do something"},
    }

    manager.async_register_service(_Elsewhere(hass))

    assert not manager._services  # noqa: SLF001
