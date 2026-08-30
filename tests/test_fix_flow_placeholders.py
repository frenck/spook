"""Every fix flow must supply the placeholders its dialog interpolates.

A dialog whose text names `{count}` while the flow hands over only `{resource}`
renders with the placeholder still in it. Nothing fails, nothing logs, and the
only way to find out is to open the repair and look at it.
"""

# pylint: disable=wrong-import-order,protected-access
from __future__ import annotations

import json
from pathlib import Path
import re

from typing import TYPE_CHECKING

import pytest

from custom_components.spook.repairs import _REMOVE_OR_IGNORE_FLOWS

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Spook ships dozens of issue types; anything near this means the file was
# read wrong rather than that they went away.
EXPECTED_ISSUES = 20

ROOT = Path(__file__).parents[1]
STRINGS = json.loads(
    (ROOT / "custom_components" / "spook" / "translations" / "en.json").read_text()
)

# Each flow is dispatched on a data key; the issues that use it carry that key.
_FLOWS = sorted(_REMOVE_OR_IGNORE_FLOWS)


def _issues_using(id_key: str) -> list[str]:
    """Return the issue translation keys whose flow is dispatched on this key."""
    source = (ROOT / "custom_components" / "spook").rglob("ectoplasms/*/repairs/*.py")
    using = []
    for path in source:
        text = path.read_text()
        if f'"{id_key}"' not in text:
            continue
        if match := re.search(r'^\s+repair = "([^"]+)"', text, re.MULTILINE):
            using.append(match.group(1))
    return using


def test_there_are_flows_to_check() -> None:
    """Guard the lookup above, which would otherwise pass by finding none."""
    assert len(_FLOWS) >= len(_REMOVE_OR_IGNORE_FLOWS)
    assert _FLOWS


@pytest.mark.parametrize("id_key", _FLOWS)
async def test_the_flow_supplies_what_its_dialog_asks_for(
    hass: HomeAssistant,
    id_key: str,
) -> None:
    """The init step's text and the flow's placeholders have to line up."""
    flow = _REMOVE_OR_IGNORE_FLOWS[id_key]

    for repair in _issues_using(id_key):
        if not (block := STRINGS["issues"].get(repair)):
            continue
        if not (fix_flow := block.get("fix_flow")):
            continue
        if not (init := fix_flow.get("step", {}).get("init")):
            continue

        needed = set(
            re.findall(
                r"\{(\w+)\}", init.get("description", "") + init.get("title", "")
            )
        )

        # What the flow hands over, read off the placeholder builder itself.
        instance = flow.__new__(flow)
        instance.hass = hass
        instance.data = dict.fromkeys(needed | {"resource"}, "x")
        supplied = set(instance._menu_placeholders())  # noqa: SLF001

        assert not needed - supplied, (
            f"{repair}: dialog names {sorted(needed - supplied)}, "
            f"{flow.__name__} supplies {sorted(supplied)}"
        )


def test_no_issue_carries_both_a_description_and_a_fix_flow() -> None:
    """Home Assistant treats those as mutually exclusive, and hassfest says so.

    An issue is either fixable, and its text lives in the fix flow, or it is
    not, and its text is the description. Carrying both fails validation with
    "two or more values in the same group of exclusion 'fixable'".

    Hassfest lives in the Home Assistant repository and cannot run here, so
    this stands in for it. Finding this in CI costs a round trip; finding it
    here costs a second.
    """
    both = sorted(
        key
        for key, block in STRINGS["issues"].items()
        if "description" in block and "fix_flow" in block
    )

    assert not both, f"these carry both, and hassfest will refuse them: {both}"


def test_there_are_issues_to_check() -> None:
    """Guard the check above, which passes happily against an empty file."""
    assert len(STRINGS["issues"]) > EXPECTED_ISSUES
