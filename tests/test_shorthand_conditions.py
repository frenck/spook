"""`condition: "{{ ... }}"` is a condition, not the name of one.

Home Assistant takes a template straight in the `condition` field as shorthand
for a template condition, and `cv.CONDITION_SCHEMA` accepts it. Spook read that
field as the name of whatever provides the condition, so it reported the entire
template back as an integration nobody has.

Reported as #1520 against Cover Control Automation, which writes conditions that
way about forty times over. Every automation built on it was flagged.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import config_validation as cv
from homeassistant.setup import async_setup_component
import pytest
import yaml

from custom_components.spook.platform_validation import (
    async_filter_unknown_condition_keys,
)
from custom_components.spook.reference_extraction import (
    extract_platform_keys_from_config,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Written the way the blueprint writes them, folded and inline.
_SHORTHAND = """
actions:
  - condition: >-
      {{
        is_sun_elevation_enabled and
        sun_elevation_mode == 'dynamic'
      }}
  - condition: "{{ state_attr(blind, 'current_position') is none }}"
  - condition: state
    entity_id: binary_sensor.real
    state: "on"
  - action: light.turn_on
"""


@pytest.mark.parametrize(
    "shorthand",
    [
        "{{ 1 > 0 }}",
        "{% if true %}yes{% endif %}",
        # A comment on its own is a template too, and core takes it.
        "{# nothing to see here #}",
    ],
)
def test_home_assistant_really_does_take_these(shorthand: str) -> None:
    """The premise. If core stops accepting them, the rest of this is moot."""
    assert cv.CONDITION_SCHEMA({"condition": shorthand})


@pytest.mark.parametrize(
    "shorthand",
    [
        "{{ 1 > 0 }}",
        "{% if true %}yes{% endif %}",
        "{# nothing to see here #}",
    ],
)
def test_no_flavour_of_template_is_read_as_a_platform(shorthand: str) -> None:
    """All three of Jinja's delimiters, comments included."""
    keys = extract_platform_keys_from_config({"conditions": [{"condition": shorthand}]})

    assert keys.condition_keys == set()


def test_a_template_condition_is_not_read_as_a_platform() -> None:
    """The name of the thing providing a condition, or the condition itself."""
    keys = extract_platform_keys_from_config(yaml.safe_load(_SHORTHAND))

    assert keys.condition_keys == {"state"}


async def test_the_shorthand_is_not_reported(hass: HomeAssistant) -> None:
    """End to end, which is where the repair reads it."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    keys = extract_platform_keys_from_config(yaml.safe_load(_SHORTHAND))

    assert await async_filter_unknown_condition_keys(hass, keys.condition_keys) == set()


async def test_a_condition_that_really_is_gone_is_still_reported(
    hass: HomeAssistant,
) -> None:
    """So none of the above can pass by the repair having stopped looking."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    config = yaml.safe_load(
        """
        conditions:
          - condition: "{{ 1 > 0 }}"
          - condition: no_such_integration_provides_this
        """,
    )
    keys = extract_platform_keys_from_config(config)

    assert await async_filter_unknown_condition_keys(hass, keys.condition_keys) == {
        "no_such_integration_provides_this",
    }
