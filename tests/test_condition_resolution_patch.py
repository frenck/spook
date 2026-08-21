"""Tests for making Spook's conditions resolvable in other domains.

Spook patches one private Home Assistant function to do this. These tests are
the alarm: if core renames or reshapes it, they fail here rather than leaving
somebody's automation quietly unable to load its condition.
"""

# pylint: disable=protected-access, wrong-import-order
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from homeassistant.helpers import condition as condition_helper
import pytest  # noqa: TC002

from custom_components.spook.condition import (
    async_get_conditions,
    async_setup_foreign_domain_conditions,
    translation_key,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_PATCHED = "_async_get_condition_platform"


def test_the_patched_function_still_exists() -> None:
    """Test the function Spook patches is where Spook expects it.

    Losing this is not a crash, it is conditions that silently stop
    resolving, so it is worth failing loudly in CI instead.
    """
    original = getattr(condition_helper, _PATCHED, None)
    assert original is not None, (
        f"Home Assistant no longer has "
        f"condition_helper.{_PATCHED}; Spook's conditions outside its own "
        f"domain need another way in"
    )

    signature = inspect.signature(original)
    assert list(signature.parameters) == ["hass", "condition_key"], signature


def test_core_still_resolves_by_key_prefix() -> None:
    """Test the reason the patch exists has not gone away.

    If core starts consulting its own provider mapping, this patch becomes
    dead weight and should be deleted rather than carried around.
    """
    source = inspect.getsource(getattr(condition_helper, _PATCHED))
    assert 'condition_key.split(".")' in source, source


def test_the_patch_restores_what_it_replaced() -> None:
    """Test unloading leaves core exactly as it was found."""
    before = getattr(condition_helper, _PATCHED)

    restore = async_setup_foreign_domain_conditions()
    assert getattr(condition_helper, _PATCHED) is not before

    restore()
    assert getattr(condition_helper, _PATCHED) is before


def test_a_missing_function_is_survivable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test Spook carries on when the function it patches is gone."""
    monkeypatch.delattr(condition_helper, _PATCHED, raising=False)

    restore = async_setup_foreign_domain_conditions()
    restore()

    assert not hasattr(condition_helper, _PATCHED)


async def test_spook_conditions_keep_their_own_namespace(
    hass: HomeAssistant,
) -> None:
    """Test conditions without a domain prefix stay under Spook.

    The patch must not quietly move Spook's own conditions somewhere else.
    """
    conditions = await async_get_conditions(hass)
    own = {key for key in conditions if not key.startswith("_")}
    assert own, conditions
    assert all(translation_key(key) == key for key in own)


async def test_other_integrations_are_left_alone(hass: HomeAssistant) -> None:
    """Test a condition Spook does not provide still goes to core."""
    restore = async_setup_foreign_domain_conditions()
    try:
        patched = getattr(condition_helper, _PATCHED)
        domain, platform = await patched(hass, "sun.is_up")
    finally:
        restore()

    assert domain == "sun"
    assert platform is not None
