"""Tests for the time in state sensor."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
)

from homeassistant import config_entries
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import State
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from custom_components.spook.integrations.spook_time_in_state.const import (
    ATTR_OBSERVED,
    ATTR_SOURCE_STATE,
    CONF_STATES,
    DOMAIN,
)

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

_SOURCE = "binary_sensor.front_door"
_SENSOR = "sensor.front_door_since"


async def _set_up(hass: HomeAssistant, states: list[str] | None = None) -> None:
    """Set the helper up for real."""
    options: dict[str, object] = {
        CONF_NAME: "Front door since",
        CONF_ENTITY_ID: _SOURCE,
    }
    if states is not None:
        options[CONF_STATES] = states
    entry = MockConfigEntry(domain=DOMAIN, title="Front door since", options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _since(hass: HomeAssistant) -> str:
    """Return what the sensor says, as the moment it holds."""
    return hass.states.get(_SENSOR).state


async def test_it_tells_since_when_the_source_changed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the moment follows each change, and says it was seen."""
    hass.states.async_set(_SOURCE, STATE_OFF)
    await _set_up(hass)
    assert hass.states.get(_SENSOR).attributes[ATTR_OBSERVED] is False

    freezer.tick(timedelta(minutes=5))
    hass.states.async_set(_SOURCE, STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(_SENSOR)
    assert state.state == dt_util.utcnow().isoformat(timespec="seconds")
    assert state.attributes[ATTR_SOURCE_STATE] == STATE_ON
    assert state.attributes[ATTR_OBSERVED] is True


async def test_a_moment_away_is_not_a_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unavailable and back to the same state keeps the moment.

    An integration reloading takes its entities away for a moment, and the
    source's own last changed starts over. A door that stayed shut did not.
    """
    hass.states.async_set(_SOURCE, STATE_OFF)
    await _set_up(hass)
    before = _since(hass)

    freezer.tick(timedelta(minutes=5))
    hass.states.async_set(_SOURCE, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=10))
    hass.states.async_set(_SOURCE, STATE_OFF)
    await hass.async_block_till_done()

    assert _since(hass) == before


async def test_a_change_of_attributes_is_not_a_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test only the state itself counts."""
    hass.states.async_set(_SOURCE, STATE_OFF)
    await _set_up(hass)
    before = _since(hass)

    freezer.tick(timedelta(minutes=5))
    hass.states.async_set(_SOURCE, STATE_OFF, {"battery": 80})
    await hass.async_block_till_done()

    assert _since(hass) == before


async def test_it_tells_since_when_the_source_last_became_a_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test with states to count, the moment stays after it changes again.

    Last opened, say: it went open, and that moment is the answer for as long
    as it does not go open again.
    """
    hass.states.async_set(_SOURCE, STATE_OFF)
    await _set_up(hass, states=[STATE_ON])
    assert hass.states.get(_SENSOR).state == "unknown"

    freezer.tick(timedelta(minutes=5))
    hass.states.async_set(_SOURCE, STATE_ON)
    await hass.async_block_till_done()
    opened = _since(hass)

    freezer.tick(timedelta(minutes=5))
    hass.states.async_set(_SOURCE, STATE_OFF)
    await hass.async_block_till_done()

    assert _since(hass) == opened
    assert hass.states.get(_SENSOR).attributes[ATTR_SOURCE_STATE] == STATE_OFF


async def test_the_moment_outlasts_a_restart(hass: HomeAssistant) -> None:
    """Test a source found where it was keeps the moment from before.

    The source's own last changed is the moment Home Assistant started, every
    start. This is the whole point of the helper.
    """
    long_ago = (dt_util.utcnow() - timedelta(days=3)).isoformat(timespec="seconds")
    mock_restore_cache(
        hass,
        [
            State(
                _SENSOR,
                long_ago,
                {ATTR_SOURCE_STATE: STATE_OFF, ATTR_OBSERVED: True},
            )
        ],
    )
    hass.states.async_set(_SOURCE, STATE_OFF)
    await _set_up(hass)

    state = hass.states.get(_SENSOR)
    assert state.state == long_ago
    assert state.attributes[ATTR_OBSERVED] is True


async def test_a_change_while_home_assistant_was_down_is_not_made_up(
    hass: HomeAssistant,
) -> None:
    """Test a source found in another state starts from now, unseen.

    It changed while nobody was looking, and when is not known. The moment it
    was noticed is the honest answer, marked as not seen happening.
    """
    long_ago = (dt_util.utcnow() - timedelta(days=3)).isoformat(timespec="seconds")
    mock_restore_cache(
        hass,
        [
            State(
                _SENSOR,
                long_ago,
                {ATTR_SOURCE_STATE: STATE_OFF, ATTR_OBSERVED: True},
            )
        ],
    )
    hass.states.async_set(_SOURCE, STATE_ON)
    await _set_up(hass)

    state = hass.states.get(_SENSOR)
    assert state.state != long_ago
    assert state.attributes[ATTR_SOURCE_STATE] == STATE_ON
    assert state.attributes[ATTR_OBSERVED] is False


async def test_the_config_flow_creates_the_helper(hass: HomeAssistant) -> None:
    """Test the flow takes a source and, optionally, the states to count."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Last motion", CONF_ENTITY_ID: _SOURCE, CONF_STATES: [STATE_ON]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Last motion"
    assert result["options"] == {
        CONF_NAME: "Last motion",
        CONF_ENTITY_ID: _SOURCE,
        CONF_STATES: [STATE_ON],
    }
