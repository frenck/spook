"""Spook - Your homie. Shared rules for triggers that watch a target.

Every trigger that watches a target's entities needs the same thing from the
configuration before it can start: a target that actually names something. The
rule lived in two of them and had already begun to drift apart in its wording,
so it lives here now.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.target import TargetSelection

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

# `TARGET_FIELDS` is a plain mapping of schema fields, so it needs compiling
# before it can validate anything.
_TARGET_SCHEMA = vol.Schema(cv.TARGET_FIELDS)


def watchable_target(value: Any) -> ConfigType:
    """Validate the target, and refuse one that names nothing.

    An empty target passes the field validation happily and then watches
    nothing at all: a trigger that loads and can never fire. Core's own target
    tracking helper raises on this for the same reason.
    """
    target: ConfigType = _TARGET_SCHEMA(value)
    if not TargetSelection(target).has_any_target:
        message = (
            "The target must name at least one entity, device, area, floor or label"
        )
        raise vol.Invalid(message)
    return target
