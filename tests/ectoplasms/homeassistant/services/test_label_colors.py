"""Tests for the label colours Spook accepts and offers."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from pathlib import Path

import voluptuous as vol
import yaml

from homeassistant.components.config.label_registry import (
    SUPPORTED_LABEL_THEME_COLORS as CORE_COLORS,
)
import pytest

from custom_components.spook.ectoplasms.homeassistant.labels import (
    SUPPORTED_LABEL_THEME_COLORS,
)

# Both label actions offer one today; the check is worthless if it finds none.
EXPECTED_PICKERS = 2

SPOOK_ROOT = Path(__file__).parents[4] / "custom_components" / "spook"
SERVICES = yaml.safe_load((SPOOK_ROOT / "services.yaml").read_text())

# Whatever offers a colour picker gets checked, so an action added later is
# covered without anybody remembering to come back here.
WITH_A_COLOUR_PICKER = sorted(
    name
    for name, action in SERVICES.items()
    if "color" in (action.get("fields") or {})
    and "select" in (action["fields"]["color"].get("selector") or {})
)


def test_the_colours_we_accept_are_the_ones_core_accepts() -> None:
    """Spook keeps its own copy rather than importing from a core component.

    A copy that drifts is the whole risk of doing it that way, so this is the
    thing that notices.
    """
    assert set(CORE_COLORS) == SUPPORTED_LABEL_THEME_COLORS


def test_there_is_something_to_check() -> None:
    """Guard the discovery above, which would otherwise pass by finding none."""
    assert len(WITH_A_COLOUR_PICKER) >= EXPECTED_PICKERS


@pytest.mark.parametrize("action", WITH_A_COLOUR_PICKER)
def test_every_colour_the_picker_offers_is_one_the_action_takes(action: str) -> None:
    """The picker used to offer five colours the schema then rejected.

    `deep_purple` and friends were written with underscores in the selector
    while the registry only ever took `deep-purple`, so picking one of those
    in the UI failed the call.
    """
    offered = [
        option["value"]
        for option in SERVICES[action]["fields"]["color"]["selector"]["select"][
            "options"
        ]
    ]
    assert offered

    validate = vol.Schema(vol.In(SUPPORTED_LABEL_THEME_COLORS))
    for value in offered:
        validate(value)

    assert set(offered) == SUPPORTED_LABEL_THEME_COLORS
