"""Tests for reading a configuration once, however many ask. #2005."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.spook import configuration_cache
from custom_components.spook.configuration_cache import per_configuration
from custom_components.spook.reference_extraction import without_disabled_steps
from custom_components.spook.template_extraction import (
    extract_template_strings_from_config,
)


def _counted() -> tuple[Any, list[Any]]:
    """Return a remembered reader, and the configurations it really read."""
    read: list[Any] = []

    @per_configuration
    def _reader(config: Any, extra: Any = None) -> int:
        _ = extra
        read.append(config)
        return len(read)

    return _reader, read


def test_the_same_configuration_is_read_once() -> None:
    """Test asking about one configuration again hands out what was read."""
    reader, read = _counted()
    config = {"actions": []}

    assert reader(config) == 1
    assert reader(config) == 1
    assert read == [config]


def test_an_equal_configuration_is_read_on_its_own() -> None:
    """Test a configuration that only looks the same is read again.

    A reload builds a new configuration, and what it says may have changed in
    a way an equal one would never show: keyed by the configuration itself,
    the new one is always read.
    """
    reader, read = _counted()

    assert reader({"actions": []}) == 1
    assert reader({"actions": []}) == 2  # noqa: PLR2004
    assert len(read) == 2  # noqa: PLR2004


@pytest.mark.parametrize("config", ["{{ x }}", 42, None, ("a", "b")])
def test_what_is_no_configuration_is_always_read(config: Any) -> None:
    """Test only a mapping or a list is remembered."""
    reader, read = _counted()

    reader(config)
    reader(config)

    assert len(read) == 2  # noqa: PLR2004


def test_anything_else_handed_in_is_always_read() -> None:
    """Test a reading that takes more than the configuration is not kept."""
    reader, read = _counted()
    config = {"actions": []}

    reader(config, "more")
    reader(config, extra="more")

    assert len(read) == 2  # noqa: PLR2004


def test_the_oldest_configuration_makes_room(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test only so many configurations are remembered, the oldest goes first."""
    monkeypatch.setattr(configuration_cache, "CACHE_SIZE", 2)
    reader, read = _counted()
    first, second, third = {"a": 1}, {"b": 2}, {"c": 3}

    reader(first)
    reader(second)
    reader(first)  # Asked again, so `second` is now the oldest.
    reader(third)
    reader(first)
    reader(second)

    assert read == [first, second, third, second]


def test_cache_clear_forgets_everything() -> None:
    """Test a cleared reader reads every configuration again."""
    reader, read = _counted()
    config = {"actions": []}

    reader(config)
    reader.cache_clear()
    reader(config)

    assert read == [config, config]


def test_disabled_steps_are_left_out_once() -> None:
    """Test the configuration without its disabled steps is worked out once.

    Every repair about automations and scripts starts with it, and they all
    get the very same copy.
    """
    config = {
        "actions": [
            {"action": "light.turn_on", "enabled": False},
            {"action": "light.turn_off"},
        ]
    }

    first = without_disabled_steps(config)

    assert first == {"actions": [{"action": "light.turn_off"}]}
    assert without_disabled_steps(config) is first


def test_templates_of_a_configuration_are_found_once() -> None:
    """Test the templates of one configuration are collected once."""
    config = {"value": "{{ states('light.kitchen') }}", "other": "plain"}

    first = extract_template_strings_from_config(config)

    assert first == ["{{ states('light.kitchen') }}"]
    assert extract_template_strings_from_config(config) is first
