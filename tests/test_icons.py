"""Tests that every trigger and condition Spook adds has an icon.

Spook shipped ten triggers and seven conditions with no `icons.json` at all,
so every one of them rendered without an icon. Nothing failed and nothing
logged: the only way to notice was to open the automation editor and look.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

SPOOK = Path(__file__).parents[1] / "custom_components" / "spook"
ICONS = json.loads((SPOOK / "icons.json").read_text())
STRINGS = json.loads((SPOOK / "translations" / "en.json").read_text())

# Home Assistant keys these by kind, and the value names the kind again.
_SECTIONS = (("triggers", "trigger"), ("conditions", "condition"))

# An `mdi:` name, lowercase with single hyphens, which is all Material Design
# Icons uses. A typo here renders as an empty square rather than an error.
_MDI = re.compile(r"\Amdi:[a-z0-9]+(-[a-z0-9]+)*\Z")


def test_there_is_something_to_check() -> None:
    """Guard the lookups, which would pass happily against an empty file."""
    assert ICONS
    for section, _ in _SECTIONS:
        assert STRINGS[section], section


@pytest.mark.parametrize(("section", "kind"), _SECTIONS)
def test_everything_translated_also_has_an_icon(section: str, kind: str) -> None:
    """The translations are the list of what Spook actually adds."""
    described = set(STRINGS[section])
    iconed = set(ICONS.get(section, {}))

    assert not described - iconed, (
        f"{section} without an icon: {sorted(described - iconed)}"
    )
    assert not iconed - described, (
        f"{section} with an icon and nothing else: {sorted(iconed - described)}"
    )

    for key, entry in ICONS[section].items():
        assert kind in entry, f"{section}.{key} does not name its {kind}"


@pytest.mark.parametrize(("section", "kind"), _SECTIONS)
def test_every_icon_is_shaped_like_an_mdi_name(section: str, kind: str) -> None:
    """A misspelled icon shows an empty square, which nothing reports."""
    for key, entry in ICONS[section].items():
        icon = entry[kind]
        assert _MDI.match(icon), f"{section}.{key} has {icon!r}"
