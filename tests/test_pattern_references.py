"""A wildcard is a pattern, not the name of anything.

Cards that take a filter read `area: KG/*` as every area under `KG`. Home
Assistant has no area called `KG/*`, so Spook looking one up and finding
nothing says nothing at all about whether the dashboard works. Reported as
#1514, against a `custom:auto-entities` card.

Areas, floors and labels only. An entity ID has a shape and `light.*` does not
have it, so that one is already turned away for a better reason.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

import yaml

from custom_components.spook.dashboard_extraction import (
    extract_areas_from_dashboard_node,
)
from custom_components.spook.reference_extraction import extract_targets_from_config

# The card from the issue, as pasted.
_AUTO_ENTITIES = """
type: custom:auto-entities
card:
  type: entities
  title: KG
  state_color: true
  show_header_toggle: true
filter:
  include:
    - domain: light
      area: KG/*
      options: {}
  exclude: []
show_empty: true
sort:
  method: friendly_name
"""


def test_the_card_from_the_issue_reports_no_areas() -> None:
    """`KG/*` is every area under KG, not an area that has gone missing."""
    assert extract_areas_from_dashboard_node(yaml.safe_load(_AUTO_ENTITIES)) == set()


def test_a_dashboard_still_finds_the_areas_it_really_names() -> None:
    """So the check above cannot pass by having stopped looking."""
    config = {
        "views": [
            {
                "cards": [
                    {"type": "area", "area": "kitchen"},
                    {
                        "type": "custom:auto-entities",
                        "filter": {
                            "include": [{"domain": "light", "area": "KG/*"}],
                        },
                    },
                    {"type": "button", "tap_action": {"area_id": ["hallway", "DG/*"]}},
                ],
            },
        ],
    }

    assert extract_areas_from_dashboard_node(config) == {"kitchen", "hallway"}


def test_an_automation_ignores_patterns_for_all_three() -> None:
    """Areas, floors and labels: whatever takes a filter can take a wildcard."""
    config = {
        "actions": [
            {
                "action": "light.turn_on",
                "target": {
                    "area_id": ["kitchen", "KG/*"],
                    "floor_id": ["ground_floor", "DG/*"],
                    "label_id": ["holiday", "seasonal_*"],
                },
            },
        ],
    }

    targets = extract_targets_from_config(config)

    assert targets.area_ids == {"kitchen"}
    assert targets.floor_ids == {"ground_floor"}
    assert targets.label_ids == {"holiday"}


def test_a_pattern_outside_a_filter_is_still_left_alone() -> None:
    """Which is the only place the wildcard rule does any work now.

    Not descending into `filter:` covers both cards that were reported, so what
    is left for this is somebody writing a pattern where patterns are not read:
    a native area card, say. Their card shows nothing and they see that at once.
    Spook saying so as well is not worth a repair, and that was the call made on
    #1517.
    """
    config = {
        "views": [
            {
                "cards": [
                    {"type": "area", "area": "KG/*"},
                    {"type": "area", "area": "kitchen"},
                ],
            },
        ],
    }

    assert extract_areas_from_dashboard_node(config) == {"kitchen"}
