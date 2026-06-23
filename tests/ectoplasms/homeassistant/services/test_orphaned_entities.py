"""Tests for Home Assistant orphaned entity services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.components.recorder import DOMAIN as RECORDER_DOMAIN
from homeassistant.components.recorder.services import (
    ATTR_KEEP_DAYS,
    SERVICE_PURGE_ENTITIES,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_RESTORED
from homeassistant.core import Context, ServiceCall
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.spook.ectoplasms.homeassistant.services import (
    delete_all_orphaned_entities,
    list_orphaned_database_entities,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from homeassistant.core import HomeAssistant


async def test_delete_all_orphaned_entities_purges_database_entities(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test database orphaned entities are passed to recorder purge."""
    calls: list[ServiceCall] = []
    context = Context()

    async def async_get_orphaned_database_entities(_: HomeAssistant) -> set[str]:
        """Return orphaned recorder entities."""
        return {"sensor.orphaned_a", "sensor.orphaned_b"}

    async def async_handle_purge_entities(call: ServiceCall) -> None:
        """Capture recorder purge service calls."""
        calls.append(call)

    monkeypatch.setattr(
        delete_all_orphaned_entities,
        "async_get_orphaned_database_entities",
        async_get_orphaned_database_entities,
    )
    hass.services.async_register(
        RECORDER_DOMAIN,
        SERVICE_PURGE_ENTITIES,
        async_handle_purge_entities,
    )

    await delete_all_orphaned_entities.SpookService(hass).async_handle_service(
        ServiceCall(
            hass,
            DOMAIN,
            "delete_all_orphaned_entities",
            {},
            context=context,
        )
    )

    assert len(calls) == 1
    assert calls[0].context is context
    assert calls[0].data[ATTR_KEEP_DAYS] == 0
    assert calls[0].data[ATTR_ENTITY_ID] == ["sensor.orphaned_a", "sensor.orphaned_b"]


async def test_get_orphaned_database_entities_uses_executor(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test orphaned database entities are fetched outside the event loop."""
    calls = []

    def list_database_entity_ids(db_url: str) -> list[str]:
        """List entity IDs stored in the recorder database."""
        calls.append(db_url)
        return ["sensor.active", "sensor.orphaned"]

    async def async_add_executor_job(func: Callable[..., Any], *args: Any) -> Any:
        """Run executor jobs inline for the test."""
        return func(*args)

    monkeypatch.setattr(
        list_orphaned_database_entities,
        "_list_database_entity_ids",
        list_database_entity_ids,
    )
    monkeypatch.setattr(hass, "async_add_executor_job", async_add_executor_job)
    hass.data.setdefault(
        "recorder_instance", type("Recorder", (), {"db_url": "sqlite://"})()
    )
    hass.states.async_set("sensor.active", "on")

    assert await list_orphaned_database_entities.async_get_orphaned_database_entities(
        hass
    ) == {"sensor.orphaned"}
    assert calls == ["sqlite://"]


async def test_delete_all_orphaned_entities_removes_restored_states(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test restored state entities are still removed locally."""
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "sensor",
        "test",
        "restored",
        suggested_object_id="restored",
    )
    hass.states.async_set("sensor.restored", "unavailable", {ATTR_RESTORED: True})
    hass.states.async_set("sensor.active", "on")

    async def async_get_orphaned_database_entities(_: HomeAssistant) -> set[str]:
        """Return no orphaned recorder entities."""
        return set()

    async def async_fail_purge_entities(_: ServiceCall) -> None:
        """Fail if recorder purge is called without orphaned entities."""
        pytest.fail("recorder.purge_entities should not be called")

    monkeypatch.setattr(
        delete_all_orphaned_entities,
        "async_get_orphaned_database_entities",
        async_get_orphaned_database_entities,
    )
    hass.services.async_register(
        RECORDER_DOMAIN,
        SERVICE_PURGE_ENTITIES,
        async_fail_purge_entities,
    )

    await delete_all_orphaned_entities.SpookService(hass).async_handle_service(
        ServiceCall(hass, DOMAIN, "delete_all_orphaned_entities", {})
    )

    assert hass.states.get("sensor.restored") is None
    assert hass.states.get("sensor.active") is not None
    assert entity_registry.async_get("sensor.restored") is None
