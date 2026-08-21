"""Tests for the automation.triggered_by_user conditions."""

# pylint: disable=protected-access

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import Context
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.condition import (
    ConditionConfig,
    async_validate_condition_config,
)
from homeassistant.helpers.script import Script
import pytest

from custom_components.spook.ectoplasms.automation.conditions.triggered_by_user import (
    SpookCondition,
)
from custom_components.spook.condition import (
    async_get_conditions,
    async_setup_foreign_domain_conditions,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(name="resolve_foreign_conditions")
def resolve_foreign_conditions_fixture() -> None:
    """Install Spook's condition resolution patch for the duration of a test."""
    restore = async_setup_foreign_domain_conditions()
    yield
    restore()


async def _run(hass: HomeAssistant, condition: dict, context: Context) -> bool:
    """Run a one-condition script and report whether the body ran.

    The condition goes through Home Assistant's own validation first, the way
    an automation's would. Skipping that step is how a single user ID stayed a
    bare string and matched nothing.
    """
    ran: list[bool] = []

    async def _mark(_call) -> None:  # noqa: ANN001
        ran.append(True)

    hass.services.async_register("test", "mark", _mark)

    validated = await async_validate_condition_config(hass, condition)
    sequence = cv.SCRIPT_SCHEMA(
        [
            {"if": [validated], "then": [{"action": "test.mark"}]},
        ]
    )
    script = Script(hass, sequence, "spook test", "test")
    await script.async_run(context=context)
    await hass.async_block_till_done()
    return bool(ran)


@pytest.mark.usefixtures("resolve_foreign_conditions")
async def test_registered_under_the_automation_domain(hass: HomeAssistant) -> None:
    """Both conditions are keyed for the automation domain, not Spook's."""
    conditions = await async_get_conditions(hass)
    assert "_automation.triggered_by_user" in conditions
    assert "_automation.not_triggered_by_user" in conditions


@pytest.mark.usefixtures("resolve_foreign_conditions")
async def test_passes_when_a_user_started_the_run(hass: HomeAssistant) -> None:
    """A run carrying a user satisfies triggered_by_user."""
    assert await _run(
        hass,
        {"condition": "automation.triggered_by_user"},
        Context(user_id="ghost-hunter"),
    )


@pytest.mark.usefixtures("resolve_foreign_conditions")
async def test_fails_when_nobody_started_the_run(hass: HomeAssistant) -> None:
    """A run with no user does not satisfy triggered_by_user."""
    assert not await _run(
        hass,
        {"condition": "automation.triggered_by_user"},
        Context(),
    )


@pytest.mark.usefixtures("resolve_foreign_conditions")
async def test_user_filter_matches(hass: HomeAssistant) -> None:
    """Naming a user narrows the condition to that user."""
    assert await _run(
        hass,
        {
            "condition": "automation.triggered_by_user",
            "options": {"user_id": "ghost-hunter"},
        },
        Context(user_id="ghost-hunter"),
    )


@pytest.mark.usefixtures("resolve_foreign_conditions")
async def test_user_filter_rejects_another_user(hass: HomeAssistant) -> None:
    """A different user does not match the filter."""
    assert not await _run(
        hass,
        {
            "condition": "automation.triggered_by_user",
            "options": {"user_id": "ghost-hunter"},
        },
        Context(user_id="somebody-else"),
    )


@pytest.mark.usefixtures("resolve_foreign_conditions")
async def test_not_triggered_by_user_is_the_inverse(hass: HomeAssistant) -> None:
    """The separate condition answers the opposite question."""
    assert await _run(
        hass, {"condition": "automation.not_triggered_by_user"}, Context()
    )
    assert not await _run(
        hass,
        {"condition": "automation.not_triggered_by_user"},
        Context(user_id="ghost-hunter"),
    )


@pytest.mark.usefixtures("resolve_foreign_conditions")
async def test_a_bare_user_id_is_not_read_as_letters(hass: HomeAssistant) -> None:
    """A condition built without validation still gets the user right.

    `set("ghost-hunter")` is a set of ten letters, and a condition that
    compares against that matches nobody while looking perfectly reasonable.
    """
    condition = SpookCondition(
        hass, ConditionConfig(options={"user_id": "ghost-hunter"})
    )
    assert condition._async_check(  # noqa: SLF001
        variables={"context": Context(user_id="ghost-hunter")}
    )
    assert not condition._async_check(  # noqa: SLF001
        variables={"context": Context(user_id="g")}
    )
