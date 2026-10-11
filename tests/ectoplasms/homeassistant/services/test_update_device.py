"""Tests for the homeassistant.update_device action."""

# pylint: disable=redefined-outer-name,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers.device_registry import DeviceEntryDisabler
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

import pytest

from custom_components.spook.ectoplasms.homeassistant.services import update_device

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        area_registry as ar,
        device_registry as dr,
        label_registry as lr,
    )

    from tests.common import MockUser


pytestmark = pytest.mark.usefixtures("spook_translations")


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the config entry the test devices belong to."""
    entry = MockConfigEntry(domain="test", title="Test")
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def device(
    config_entry: MockConfigEntry, device_registry: dr.DeviceRegistry
) -> dr.DeviceEntry:
    """Return a device, named the way its integration named it."""
    return device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "speaker")},
        manufacturer="Spook",
        model="Ghost",
        name="Speaker",
    )


@pytest.fixture
def loud_label(label_registry: lr.LabelRegistry) -> lr.LabelEntry:
    """Return a label that exists, for a call to name next to one that does not."""
    return label_registry.async_create("Loud")


async def _setup(hass: HomeAssistant) -> None:
    """Register the action."""
    assert await async_setup_component(hass, "homeassistant", {})
    update_device.SpookService(hass).async_register()
    await hass.async_block_till_done()


async def _update(
    hass: HomeAssistant, context: Context | None = None, **data: object
) -> None:
    """Call the action."""
    await hass.services.async_call(
        "homeassistant", "update_device", dict(data), blocking=True, context=context
    )


async def test_every_field_can_be_changed(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
    device: dr.DeviceEntry,
) -> None:
    """Each field the UI can change, changed through the action itself."""
    area = area_registry.async_create("Living room")
    label = label_registry.async_create("Loud")
    await _setup(hass)

    await _update(
        hass,
        device_id=device.id,
        name_by_user="Living room speaker",
        area_id=area.id,
        labels=[label.label_id],
        disabled_by="user",
    )

    updated = device_registry.async_get(device.id)
    assert updated.name_by_user == "Living room speaker"
    assert updated.area_id == area.id
    assert updated.labels == {label.label_id}
    assert updated.disabled_by is DeviceEntryDisabler.USER

    # What the integration owns is not touched by any of it.
    assert updated.name == "Speaker"
    assert updated.manufacturer == "Spook"
    assert updated.model == "Ghost"


async def test_it_leaves_alone_what_the_call_did_not_mention(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
    device: dr.DeviceEntry,
) -> None:
    """Renaming a device should not take it out of its area.

    Passing every field through would read an unmentioned area as "take it
    out of its area".
    """
    area = area_registry.async_create("Living room")
    label = label_registry.async_create("Loud")
    device_registry.async_update_device(
        device.id,
        area_id=area.id,
        labels={label.label_id},
        name_by_user="Speaker",
    )
    await _setup(hass)

    await _update(hass, device_id=device.id, name_by_user="Living room speaker")

    updated = device_registry.async_get(device.id)
    assert updated.name_by_user == "Living room speaker"
    assert updated.area_id == area.id
    assert updated.labels == {label.label_id}
    assert updated.disabled_by is None


async def test_null_gives_the_integration_name_back_and_clears_the_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    device: dr.DeviceEntry,
) -> None:
    """The UI can reset a name to the integration's, so this can too."""
    area = area_registry.async_create("Living room")
    device_registry.async_update_device(
        device.id, area_id=area.id, name_by_user="Living room speaker"
    )
    await _setup(hass)

    await _update(hass, device_id=device.id, name_by_user=None, area_id=None)

    updated = device_registry.async_get(device.id)
    assert updated.name_by_user is None
    assert updated.area_id is None
    assert updated.name == "Speaker"


async def test_labels_are_replaced_and_an_empty_list_clears_them(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    label_registry: lr.LabelRegistry,
    device: dr.DeviceEntry,
) -> None:
    """Replaced, like the UI does.

    Adding or removing one is what the add and remove actions are for.
    """
    loud = label_registry.async_create("Loud")
    quiet = label_registry.async_create("Quiet")
    device_registry.async_update_device(device.id, labels={loud.label_id})
    await _setup(hass)

    await _update(hass, device_id=device.id, labels=quiet.label_id)
    assert device_registry.async_get(device.id).labels == {quiet.label_id}

    await _update(hass, device_id=device.id, labels=[])
    assert device_registry.async_get(device.id).labels == set()


async def test_null_enables_a_disabled_device_again(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    device: dr.DeviceEntry,
) -> None:
    """The other half of disabling: without it, a disabled device stays so."""
    device_registry.async_update_device(device.id, disabled_by=DeviceEntryDisabler.USER)
    await _setup(hass)

    await _update(hass, device_id=device.id, disabled_by=None)

    assert device_registry.async_get(device.id).disabled_by is None


async def test_a_child_device_is_updated_and_enabled_with_its_parent(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    device: dr.DeviceEntry,
) -> None:
    """A child device has its own update method in the registry.

    Home Assistant will not enable a child device while its parent is
    disabled, so the parent is enabled along with it, the way enable_device
    does it.
    """
    area = area_registry.async_create("Living room")
    child = device_registry.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "speaker-left")},
        name="Left",
        parent_device_id=device.id,
    )
    device_registry.async_update_child_device(
        child.id, disabled_by=DeviceEntryDisabler.USER
    )
    device_registry.async_update_device(device.id, disabled_by=DeviceEntryDisabler.USER)
    await _setup(hass)

    await _update(
        hass,
        device_id=child.id,
        name_by_user="Left speaker",
        area_id=area.id,
        disabled_by=None,
    )

    updated = device_registry.async_get(child.id)
    assert updated.name_by_user == "Left speaker"
    assert updated.area_id == area.id
    assert updated.disabled_by is None
    assert device_registry.async_get(device.id).disabled_by is None


async def test_disabling_the_last_enabled_child_disables_its_parent(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    device: dr.DeviceEntry,
) -> None:
    """The same way disable_device does it."""
    child = device_registry.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "speaker-left")},
        name="Left",
        parent_device_id=device.id,
    )
    await _setup(hass)

    await _update(hass, device_id=child.id, disabled_by="user")

    assert device_registry.async_get(child.id).disabled_by is DeviceEntryDisabler.USER
    assert device_registry.async_get(device.id).disabled_by is DeviceEntryDisabler.USER


async def test_only_a_user_can_be_the_one_who_disabled_it(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    device: dr.DeviceEntry,
) -> None:
    """The other reasons are Home Assistant's to set, not an automation's."""
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await _update(hass, device_id=device.id, disabled_by="integration")

    assert device_registry.async_get(device.id).disabled_by is None


async def test_a_device_that_does_not_exist_is_refused(
    hass: HomeAssistant,
) -> None:
    """Core raises a bare KeyError on this, which surfaces as an unknown error."""
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match=r"Device no_such_device not found"):
        await _update(hass, device_id="no_such_device", name_by_user="Ghost")


async def test_a_call_that_changes_nothing_is_refused(
    hass: HomeAssistant,
    device: dr.DeviceEntry,
) -> None:
    """A misspelled field name would otherwise be a successful no-op."""
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match="Nothing to update"):
        await _update(hass, device_id=device.id)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"area_id": "attic"}, "Area attic not found"),
        ({"labels": ["loud", "no_such_label"]}, "Label no_such_label not found"),
    ],
)
@pytest.mark.usefixtures("loud_label")
async def test_an_unknown_reference_is_refused(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    device: dr.DeviceEntry,
    data: dict[str, object],
    message: str,
) -> None:
    """The registry stores an area or label that does not exist without a word.

    Nothing is changed either, not even the part of the call that was fine.
    """
    await _setup(hass)

    with pytest.raises(HomeAssistantError, match=message):
        await _update(hass, device_id=device.id, name_by_user="Ghost", **data)

    unchanged = device_registry.async_get(device.id)
    assert unchanged.name_by_user is None
    assert unchanged.area_id is None
    assert unchanged.labels == set()


async def test_only_an_admin_can_update_a_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_read_only_user: MockUser,
    device: dr.DeviceEntry,
) -> None:
    """Devices are the same for every user, so changing one takes an admin."""
    await _setup(hass)

    with pytest.raises(Unauthorized):
        await _update(
            hass,
            context=Context(user_id=hass_read_only_user.id),
            device_id=device.id,
            name_by_user="Ghost",
        )

    assert device_registry.async_get(device.id).name_by_user is None
