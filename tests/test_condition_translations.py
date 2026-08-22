"""Tests for Spook condition descriptors and translations.

Spook's conditions come in two shapes. Its own live under `spook.` and are
described in `conditions.yaml` like any integration's. The ones it registers
in another integration's domain cannot be: hassfest requires underscore-slug
keys there, and `automation.triggered_by_user` names a domain. Those live in
`foreign_conditions.yaml` and are injected at runtime.

Both shapes still need a descriptor and a translation, so these tests compare
on the absolute key, using the same helpers the code uses rather than a copy
of the convention.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from custom_components.spook.condition import async_get_conditions, condition_schema_key
from custom_components.spook.const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SPOOK_ROOT = Path(__file__).parents[1] / "custom_components" / DOMAIN


def _descriptors() -> dict:
    """Return every descriptor Spook ships, keyed the way Spook keys them.

    One file, one key shape, the same as the actions: a condition belonging to
    another domain is written `domain_name`, which hassfest accepts and which
    doubles as its translation key.
    """
    return yaml.safe_load((SPOOK_ROOT / "conditions.yaml").read_text())


def _translations() -> dict:
    """Return the English condition translations."""
    return json.loads((SPOOK_ROOT / "translations" / "en.json").read_text())[
        "conditions"
    ]


async def test_every_condition_has_a_descriptor(hass: HomeAssistant) -> None:
    """Test every discovered condition is described somewhere."""
    discovered = {condition_schema_key(key) for key in await async_get_conditions(hass)}
    assert discovered == set(_descriptors())


async def test_no_descriptor_key_has_a_dot(hass: HomeAssistant) -> None:
    """Test the descriptor keys stay in the shape hassfest demands.

    `conditions.yaml` keys have to be underscore slugs. A dotted key is a hard
    CI failure, not a warning, and it is an easy mistake to make because the
    condition itself is registered with a dot in it.
    """
    assert all("." not in key for key in _descriptors())

    foreign = [
        key
        for key in await async_get_conditions(hass)
        if condition_schema_key(key) != key
    ]
    assert foreign, "no foreign-domain conditions found to check"
    for key in foreign:
        assert "." in key
        assert condition_schema_key(key) in _descriptors()


def test_every_condition_has_translations() -> None:
    """Test every described condition has a matching translation.

    A condition keyed for another integration's domain cannot use that key in
    Spook's own translation file, so it is filed under `domain_name`, the same
    shape the actions use.
    """
    assert set(_descriptors()) == set(_translations())


def test_every_condition_field_has_translations() -> None:
    """Test every described condition field has a matching translation.

    A field without a translation renders as its raw key in the UI, which is
    the kind of thing nobody notices until a user screenshots it.
    """
    translations = _translations()

    for condition, descriptor in _descriptors().items():
        described = set((descriptor or {}).get("fields", {}))
        translated = set(translations[condition].get("fields", {}))
        assert described == translated, condition


def test_condition_translation_names_do_not_include_ghost() -> None:
    """Test condition translation names do not include Spook's ghost marker.

    The ghost is added while injecting, so having one in the file would give
    the reader two of them.
    """
    assert all("👻" not in condition["name"] for condition in _translations().values())
