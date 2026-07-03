"""Spook - Your homie. Validation of trigger and condition platform keys.

Triggers and conditions are pluggable: integrations provide them and keys
like ``samsung_tv.turned_on`` resolve to an integration at load time. When
that integration is gone, the automation fails validation and Home
Assistant only raises a generic issue. These helpers determine which keys
cannot be provided by any available integration.

A key is only reported as unknown when its integration does not exist at
all, or exists but ships no trigger/condition platform. Integrations that
exist but are not loaded yet are never reported.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# The alias tables and registries are internal Home Assistant details;
# the nightly canary and the tests guard these imports.
from homeassistant.helpers.condition import (
    _PLATFORM_ALIASES as _CONDITION_PLATFORM_ALIASES,
    CONDITIONS,
)
from homeassistant.helpers.trigger import (
    _PLATFORM_ALIASES as _TRIGGER_PLATFORM_ALIASES,
    TRIGGERS,
)
from homeassistant.loader import IntegrationNotFound, async_get_integration

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from homeassistant.core import HomeAssistant
    from homeassistant.util.hass_dict import HassKey


async def _async_filter_unknown_keys(
    hass: HomeAssistant,
    *,
    keys: Iterable[str],
    registry_key: HassKey[dict[str, str]],
    aliases: Mapping[str | None, str | None],
    platform_file: str,
) -> set[str]:
    """Return the platform keys that no available integration can provide."""
    registered: dict[str, str] = hass.data.get(registry_key) or {}
    registered_domains = set(registered.values())

    unknown = set()
    for key in keys:
        if not key or not isinstance(key, str) or key in registered:
            continue

        domain = key.partition(".")[0]
        if "." not in key:
            # Aliases only apply to bare keys; ``None`` marks a built-in.
            domain = aliases.get(domain, domain)  # type: ignore[assignment]
            if domain is None:
                continue

        # The integration registered its platform; whether this specific
        # key exists on it is validated by Home Assistant itself.
        if domain in registered_domains:
            continue

        try:
            integration = await async_get_integration(hass, domain)
        except IntegrationNotFound:
            unknown.add(key)
            continue

        # The integration exists but is not loaded (so nothing registered
        # yet); only report when it cannot provide this platform at all.
        if not integration.platforms_exists((platform_file,)):
            unknown.add(key)

    return unknown


async def async_filter_unknown_trigger_keys(
    hass: HomeAssistant,
    keys: Iterable[str],
) -> set[str]:
    """Return the trigger keys that no available integration can provide."""
    return await _async_filter_unknown_keys(
        hass,
        keys=keys,
        registry_key=TRIGGERS,
        aliases=_TRIGGER_PLATFORM_ALIASES,
        platform_file="trigger",
    )


async def async_filter_unknown_condition_keys(
    hass: HomeAssistant,
    keys: Iterable[str],
) -> set[str]:
    """Return the condition keys that no available integration can provide."""
    return await _async_filter_unknown_keys(
        hass,
        keys=keys,
        registry_key=CONDITIONS,
        aliases=_CONDITION_PLATFORM_ALIASES,
        platform_file="condition",
    )
