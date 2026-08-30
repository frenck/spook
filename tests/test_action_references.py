"""Every action Spook names in its own words has to be one that exists.

Spook told people to clear orphaned statistics with `recorder.clear_statistics`
for as long as that repair existed. There is no such action: it is a websocket
command the Developer Tools statistics page calls, and nothing anybody can find
under Developer Tools > Actions. Reported as #1510 by somebody who went looking
for it and could not find it.
"""

from __future__ import annotations

import json
import pathlib
import re

import homeassistant
import yaml

SPOOK = pathlib.Path(__file__).parents[1] / "custom_components" / "spook"
DOCUMENTATION = pathlib.Path(__file__).parents[1] / "documentation"
CORE = pathlib.Path(homeassistant.__file__).parent / "components"

# Something in backticks, called an action in the very next word. That is a
# claim about what somebody will find in Home Assistant, and it either holds
# or it does not.
_CLAIMED_AS_AN_ACTION = re.compile(r"`([a-z_]+\.[a-z_]+)`\s+action\b")

# Notify services are named after whoever set them up, so these stand for
# "your phone" rather than naming anything that exists anywhere.
_STANDS_FOR_YOUR_OWN = {"notify.my_phone", "notify.phone"}

# If the wording drifts and the pattern stops matching, this test would pass by
# having nothing left to check. It has to keep finding at least what it found
# the day it was written.
_AT_LEAST_THIS_MANY = 10


def _referenced() -> set[tuple[str, str]]:
    """Return every action Spook calls an action, and where it says so."""
    found = {
        (ref, "translations/en.json")
        for ref in _CLAIMED_AS_AN_ACTION.findall(
            json.dumps(json.loads((SPOOK / "translations" / "en.json").read_text())),
        )
    }
    for markdown in DOCUMENTATION.rglob("*.md"):
        found |= {
            (ref, str(markdown.relative_to(DOCUMENTATION.parent)))
            for ref in _CLAIMED_AS_AN_ACTION.findall(markdown.read_text())
        }

    return found


def _exists(action: str) -> bool:
    """Return whether Home Assistant or Spook actually offers this action."""
    domain, _, service = action.partition(".")

    spook_services = yaml.safe_load((SPOOK / "services.yaml").read_text()) or {}
    if f"{domain}_{service}" in spook_services:
        return True

    descriptor = CORE / domain / "services.yaml"
    if not descriptor.is_file():
        return False

    try:
        return service in (yaml.safe_load(descriptor.read_text()) or {})
    except yaml.YAMLError:
        return False


def test_every_action_spook_names_is_one_that_exists() -> None:
    """Telling somebody to use an action that is not there wastes their evening."""
    referenced = _referenced()

    assert len(referenced) >= _AT_LEAST_THIS_MANY, (
        f"only found {len(referenced)} action references, so the wording has "
        f"moved and this test has stopped looking at anything: {referenced}"
    )

    missing = sorted(
        f"{action} ({where})"
        for action, where in referenced
        if action not in _STANDS_FOR_YOUR_OWN and not _exists(action)
    )
    assert not missing, "Spook names actions that do not exist: " + ", ".join(missing)
