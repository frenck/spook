"""Tests for the spook.triggered_by_user conditions."""

# ruff: noqa: SLF001
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
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.spook.conditions.triggered_by_user import (
    SpookCondition,
)
from custom_components.spook.condition import async_get_conditions

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


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


async def test_both_conditions_are_discovered(hass: HomeAssistant) -> None:
    """Both conditions turn up in Spook's own discovery, under plain keys.

    Plain, because Home Assistant prefixes them with the providing
    integration itself: these are `spook.triggered_by_user` and
    `spook.not_triggered_by_user` by the time anybody writes one in YAML.
    """
    conditions = await async_get_conditions(hass)
    assert "triggered_by_user" in conditions
    assert "not_triggered_by_user" in conditions


async def test_passes_when_a_user_started_the_run(hass: HomeAssistant) -> None:
    """A run carrying a user satisfies triggered_by_user."""
    assert await _run(
        hass,
        {"condition": "spook.triggered_by_user"},
        Context(user_id="ghost-hunter"),
    )


async def test_fails_when_nobody_started_the_run(hass: HomeAssistant) -> None:
    """A run with no user does not satisfy triggered_by_user."""
    assert not await _run(
        hass,
        {"condition": "spook.triggered_by_user"},
        Context(),
    )


async def _person(hass: HomeAssistant, name: str, *, linked: bool = True) -> str:
    """Set up a person, optionally linked to a user account, and return its ID."""
    user_id = None
    if linked:
        user = await hass.auth.async_create_user(name)
        user_id = user.id

    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {"id": name.lower(), "name": name, "user_id": user_id}
                if user_id
                else {"id": name.lower(), "name": name}
            ]
        },
    )
    await hass.async_block_till_done()
    return user_id


async def test_person_filter_matches(hass: HomeAssistant) -> None:
    """Naming a person narrows the condition to the account they are linked to."""
    user_id = await _person(hass, "Frenck")

    assert await _run(
        hass,
        {
            "condition": "spook.triggered_by_user",
            "options": {"person": "person.frenck"},
        },
        Context(user_id=user_id),
    )


async def test_person_filter_rejects_another_user(hass: HomeAssistant) -> None:
    """Somebody else's account does not match the named person."""
    await _person(hass, "Frenck")

    assert not await _run(
        hass,
        {
            "condition": "spook.triggered_by_user",
            "options": {"person": "person.frenck"},
        },
        Context(user_id="somebody-else"),
    )


async def test_person_without_an_account_never_matches(hass: HomeAssistant) -> None:
    """A person with no user account linked has nothing to match against.

    Worth pinning: it is a quiet way for a condition to never pass, and the
    description says so precisely because of this.
    """
    await _person(hass, "Frenck", linked=False)

    assert not await _run(
        hass,
        {
            "condition": "spook.triggered_by_user",
            "options": {"person": "person.frenck"},
        },
        Context(user_id="anyone-at-all"),
    )


async def test_an_unknown_person_is_skipped(hass: HomeAssistant) -> None:
    """A person entity that does not exist does not blow up the check."""
    assert not await _run(
        hass,
        {
            "condition": "spook.triggered_by_user",
            "options": {"person": "person.long_gone"},
        },
        Context(user_id="somebody"),
    )


async def test_not_triggered_by_user_is_the_inverse(hass: HomeAssistant) -> None:
    """The separate condition answers the opposite question."""
    assert await _run(hass, {"condition": "spook.not_triggered_by_user"}, Context())
    assert not await _run(
        hass,
        {"condition": "spook.not_triggered_by_user"},
        Context(user_id="ghost-hunter"),
    )


async def test_a_bare_person_id_is_not_read_as_letters(hass: HomeAssistant) -> None:
    """A condition built without validation still reads one person correctly.

    Validation turns a single entity ID into a list. Handed to a condition
    raw, a bare string iterated character by character matches nobody while
    looking perfectly reasonable.
    """
    user_id = await _person(hass, "Frenck")

    condition = SpookCondition(
        hass, ConditionConfig(options={"person": "person.frenck"})
    )
    assert condition._async_check(variables={"context": Context(user_id=user_id)})
    assert not condition._async_check(variables={"context": Context(user_id="p")})
