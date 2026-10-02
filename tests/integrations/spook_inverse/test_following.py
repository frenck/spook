"""Tests for an inverse keeping up with its source."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er

from custom_components.spook.integrations.spook_inverse import MIGRATION_MINOR_VERSION
from custom_components.spook.integrations.spook_inverse.const import (
    CONF_HIDE_SOURCE,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _source(hass: HomeAssistant, object_id: str, state: str = STATE_OFF) -> str:
    """Register a switch to invert, and give it a state."""
    entity_id = (
        er.async_get(hass)
        .async_get_or_create("switch", "test", object_id, suggested_object_id=object_id)
        .entity_id
    )
    hass.states.async_set(entity_id, state)
    return entity_id


async def _inverse(
    hass: HomeAssistant,
    source: str,
    *,
    hide_source: bool = False,
) -> tuple[MockConfigEntry, str]:
    """Set an inverse of this source up for real, and return its entity ID."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Inverted",
        version=1,
        minor_version=MIGRATION_MINOR_VERSION,
        options={
            CONF_ENTITY_ID: source,
            CONF_HIDE_SOURCE: hide_source,
            "inverse_type": "switch",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    (inverse,) = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    return entry, inverse.entity_id


async def test_a_source_going_unavailable_takes_the_inverse_with_it(
    hass: HomeAssistant,
) -> None:
    """Test the inverse does not keep showing what it was before.

    It noted the source was gone and never said so, so dashboards and
    automations went on reading the last state it had.
    """
    source = _source(hass, "lamp", STATE_OFF)
    _entry, inverse = await _inverse(hass, source)
    assert hass.states.get(inverse).state == STATE_ON

    hass.states.async_set(source, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    assert hass.states.get(inverse).state == STATE_UNAVAILABLE


async def test_a_renamed_source_is_followed(hass: HomeAssistant) -> None:
    """Test renaming the source does not cut the inverse loose."""
    source = _source(hass, "lamp", STATE_OFF)
    entry, inverse = await _inverse(hass, source)

    er.async_get(hass).async_update_entity(source, new_entity_id="switch.renamed")
    hass.states.async_set("switch.renamed", STATE_ON)
    await hass.async_block_till_done()

    assert entry.options[CONF_ENTITY_ID] == "switch.renamed"
    assert hass.states.get(inverse).state == STATE_OFF


async def test_a_source_given_by_its_registry_id_is_followed(
    hass: HomeAssistant,
) -> None:
    """Test a source stored as its registry ID is not stuck unavailable."""
    source = _source(hass, "lamp", STATE_OFF)
    registry_id = er.async_get(hass).async_get(source).id
    _entry, inverse = await _inverse(hass, registry_id)

    assert hass.states.get(inverse).state == STATE_ON


async def test_pointing_it_elsewhere_shows_the_old_source_again(
    hass: HomeAssistant,
) -> None:
    """Test the source this inverse hid comes back once it is not the source."""
    first = _source(hass, "first")
    second = _source(hass, "second")
    entry, _inverse_id = await _inverse(hass, first, hide_source=True)
    registry = er.async_get(hass)
    registry.async_update_entity(first, hidden_by=er.RegistryEntryHider.INTEGRATION)

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_ENTITY_ID: second}
    )
    await hass.async_block_till_done()

    assert registry.async_get(first).hidden_by is None


async def test_a_source_another_inverse_hides_stays_hidden(
    hass: HomeAssistant,
) -> None:
    """Test one inverse moving on does not undo another one's hiding."""
    first = _source(hass, "first")
    second = _source(hass, "second")
    entry, _inverse_id = await _inverse(hass, first, hide_source=True)
    await _inverse(hass, first, hide_source=True)
    registry = er.async_get(hass)
    registry.async_update_entity(first, hidden_by=er.RegistryEntryHider.INTEGRATION)

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_ENTITY_ID: second}
    )
    await hass.async_block_till_done()

    assert registry.async_get(first).hidden_by is er.RegistryEntryHider.INTEGRATION


async def test_saving_options_leaves_a_source_hidden_by_hand_alone(
    hass: HomeAssistant,
) -> None:
    """Test the options do not overrule somebody hiding the source themselves."""
    source = _source(hass, "lamp")
    entry, _inverse_id = await _inverse(hass, source)
    registry = er.async_get(hass)
    registry.async_update_entity(source, hidden_by=er.RegistryEntryHider.USER)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENTITY_ID: source, CONF_HIDE_SOURCE: False},
    )
    await hass.async_block_till_done()

    assert registry.async_get(source).hidden_by is er.RegistryEntryHider.USER


async def test_turning_hiding_off_shows_the_source_again(
    hass: HomeAssistant,
) -> None:
    """Test switching "hide source" off gives the source back."""
    source = _source(hass, "lamp")
    entry, _inverse_id = await _inverse(hass, source, hide_source=True)
    registry = er.async_get(hass)
    registry.async_update_entity(source, hidden_by=er.RegistryEntryHider.INTEGRATION)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENTITY_ID: source, CONF_HIDE_SOURCE: False},
    )
    await hass.async_block_till_done()

    assert registry.async_get(source).hidden_by is None


async def test_one_inverse_letting_go_does_not_unhide_for_the_other(
    hass: HomeAssistant,
) -> None:
    """Test two inverses of one source share the hiding."""
    source = _source(hass, "lamp")
    entry, _inverse_id = await _inverse(hass, source, hide_source=True)
    await _inverse(hass, source, hide_source=True)
    registry = er.async_get(hass)
    registry.async_update_entity(source, hidden_by=er.RegistryEntryHider.INTEGRATION)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ENTITY_ID: source, CONF_HIDE_SOURCE: False},
    )
    await hass.async_block_till_done()

    assert registry.async_get(source).hidden_by is er.RegistryEntryHider.INTEGRATION


async def test_a_source_this_inverse_never_hid_is_not_unhidden(
    hass: HomeAssistant,
) -> None:
    """Test moving on from a source does not undo somebody else's hiding."""
    first = _source(hass, "first")
    second = _source(hass, "second")
    entry, _inverse_id = await _inverse(hass, first, hide_source=False)
    registry = er.async_get(hass)
    registry.async_update_entity(first, hidden_by=er.RegistryEntryHider.INTEGRATION)

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_ENTITY_ID: second}
    )
    await hass.async_block_till_done()

    assert registry.async_get(first).hidden_by is er.RegistryEntryHider.INTEGRATION


async def test_a_removed_source_by_registry_id_still_sets_up(
    hass: HomeAssistant,
) -> None:
    """Test a source stored by a registry ID that is gone does not fail setup."""
    source = _source(hass, "lamp")
    registry = er.async_get(hass)
    registry_id = registry.async_get(source).id
    registry.async_remove(source)

    entry, inverse = await _inverse(hass, registry_id)

    assert entry.state.recoverable
    assert hass.states.get(inverse).state == STATE_UNAVAILABLE
