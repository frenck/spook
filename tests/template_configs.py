"""Shared configurations for tests that read templates out of a config."""

from __future__ import annotations

from typing import Any

import pytest


def shadowing_configs(name: str, template: str) -> list[Any]:
    """Return a configuration for each place that can give `name` a meaning.

    Each also uses `template` in a step, so only the name stands in its way.
    """
    step = {"wait_template": template}
    return [
        pytest.param({"variables": {name: {}}, "actions": [step]}, id="variables"),
        pytest.param(
            {"trigger_variables": {name: {}}, "actions": [step]},
            id="trigger variables",
        ),
        pytest.param(
            {
                "triggers": [
                    {"trigger": "event", "event_type": "x", "variables": {name: 1}}
                ],
                "actions": [step],
            },
            id="variables of a trigger",
        ),
        pytest.param(
            {"actions": [{"variables": {name: {}}}, step]},
            id="variables step",
        ),
        pytest.param(
            {"fields": {name: {"selector": {"text": {}}}}, "sequence": [step]},
            id="script field",
        ),
        pytest.param(
            {
                "actions": [
                    {"action": "script.spooky", "response_variable": name},
                    step,
                ]
            },
            id="response variable",
        ),
    ]
