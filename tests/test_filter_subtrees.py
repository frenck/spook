"""What a filter selects is not a reference to anything in particular.

Two reports came out of the same block of the same card. #1514 was
`area: KG/*`, meaning every area under KG. #1468 was `entity: this.entity_id`
under `options`, standing for whichever entity matched. Both were read as
references and both were reported as things that had gone missing.

Each was first answered by naming the string, and a list of names is a thing to
maintain and a thing to be caught out by. The matcher itself is the thing worth
skipping, and that came from two reviewers and a reporter arriving at it
separately.

`options` is the exception, and not descending into it was a mistake caught in
review: it is card configuration handed to each match rather than part of the
selection, and it can name entities outright.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from custom_components.spook.dashboard_extraction import (
    extract_areas_from_dashboard_node,
    extract_entities_from_dashboard_node,
)
from custom_components.spook.entity_filtering import async_filter_known_entity_ids

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# The card from #1468, as the reporter pasted it.
_PLACEHOLDER_IN_OPTIONS = """
type: custom:auto-entities
filter:
  include:
    - entity_id: sensor.some_prefix*
      state: "> 0"
      options:
        entity: this.entity_id
"""

# The card from #1514, as that reporter pasted it.
_WILDCARD_AREA = """
type: custom:auto-entities
card:
  type: entities
  title: KG
filter:
  include:
    - domain: light
      area: KG/*
      options: {}
  exclude: []
"""


async def test_a_placeholder_inside_options_is_not_reported(
    hass: HomeAssistant,
) -> None:
    """#1468. It stands for whichever entity matched, so it names none of them.

    Collected, because `options` is configuration and gets walked, then turned
    away at the gate for not being an entity anybody could have. Two layers,
    and this is the one that decides.
    """
    extracted = extract_entities_from_dashboard_node(
        yaml.safe_load(_PLACEHOLDER_IN_OPTIONS),
    )

    assert (
        async_filter_known_entity_ids(
            hass,
            entity_ids=extracted,
            known_entity_ids=set(),
        )
        == set()
    )


def test_an_area_pattern_inside_a_filter_is_never_collected() -> None:
    """#1514. `KG/*` is every area under KG, not an area that has gone."""
    assert extract_areas_from_dashboard_node(yaml.safe_load(_WILDCARD_AREA)) == set()


def test_an_entity_named_inside_options_is_still_read() -> None:
    """`options` is not a matcher, whatever sits beside it in the filter.

    It is card configuration handed to each match, and it can hold a nested
    card naming entities outright. Those are drawn on the dashboard, so one
    that has gone is worth saying. Skipping the whole filter subtree lost them,
    which is what review caught.
    """
    config = yaml.safe_load(
        """
        type: custom:auto-entities
        filter:
          include:
            - domain: light
              area: KG/*
              options:
                type: horizontal-stack
                cards:
                  - type: entity
                    entity: sensor.pinned_in_every_row
        """,
    )

    assert extract_entities_from_dashboard_node(config) == {
        "sensor.pinned_in_every_row",
    }
    assert extract_areas_from_dashboard_node(config) == set()


def test_the_card_a_filter_decorates_is_still_read() -> None:
    """A filter card still has a card, and that one names things for real."""
    config = yaml.safe_load(
        """
        type: custom:auto-entities
        card:
          type: entities
          entities:
            - sensor.a_real_one
        filter:
          include:
            - entity_id: sensor.some_prefix*
        """,
    )

    assert extract_entities_from_dashboard_node(config) == {"sensor.a_real_one"}


def test_everything_outside_a_filter_is_still_read() -> None:
    """So none of the above can pass by the walk having given up entirely."""
    config = yaml.safe_load(
        """
        views:
          - cards:
              - type: entities
                entities:
                  - light.hallway
              - type: area
                area: kitchen
              - type: custom:auto-entities
                filter:
                  include:
                    - area: KG/*
                      state: "> 0"
        """,
    )

    assert extract_entities_from_dashboard_node(config) == {"light.hallway"}
    assert extract_areas_from_dashboard_node(config) == {"kitchen"}
