"""What is under a `filter:` says which entities to pick, not which one is meant.

Two reports came out of the same block of the same card. #1468 was
`entity: this.entity_id` under `options`, a placeholder standing for whichever
entity matched. #1514 was `area: KG/*`, meaning every area under KG. Both were
read as references and both were reported as things that had gone missing.

Named strings were the first answer to each, and a list of them is a thing to
maintain and a thing to be caught out by. Not descending is the answer to the
whole class, and it came from two reviewers and a reporter arriving at it
separately.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

import yaml

from custom_components.spook.dashboard_extraction import (
    extract_areas_from_dashboard_node,
    extract_entities_from_dashboard_node,
)

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


def test_a_placeholder_inside_a_filter_is_never_collected() -> None:
    """#1468. It stands for whichever entity matched, so it names none of them."""
    assert (
        extract_entities_from_dashboard_node(
            yaml.safe_load(_PLACEHOLDER_IN_OPTIONS),
        )
        == set()
    )


def test_an_area_pattern_inside_a_filter_is_never_collected() -> None:
    """#1514. `KG/*` is every area under KG, not an area that has gone."""
    assert extract_areas_from_dashboard_node(yaml.safe_load(_WILDCARD_AREA)) == set()


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
              options:
                entity: this.entity_id
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
                      options:
                        entity: this.entity_id
        """,
    )

    assert extract_entities_from_dashboard_node(config) == {"light.hallway"}
    assert extract_areas_from_dashboard_node(config) == {"kitchen"}
