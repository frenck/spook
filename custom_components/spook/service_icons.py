"""Spook - Your homie. Icons for the actions Spook adds to other integrations.

Home Assistant looks the icon of an action up in the icons of the domain the
action belongs to. Most of Spook's actions belong to a domain that is not
Spook's, like `light.increase_brightness`, so the icons in Spook's own
icons.json never reach them. This puts them where Home Assistant looks, the
same way Spook already does for the names and descriptions of those actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.icon import ICON_CACHE, async_get_icons

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant

ICON_CATEGORY = "services"


@callback
def _async_service_icon_cache(hass: HomeAssistant) -> dict[str, Any] | None:
    """Return Home Assistant's cache of action icons, by domain.

    The cache is internal to Home Assistant. Should its shape change, the
    icons are skipped and the actions keep the icon of their domain, rather
    than Spook failing to set up over a picture.
    """
    try:
        # pylint: disable-next=protected-access
        categories = hass.data[ICON_CACHE]._cache  # noqa: SLF001
    except AttributeError, KeyError:
        LOGGER.warning(
            "Unable to access Home Assistant's icon cache, "
            "skipping the icons of Spook's actions"
        )
        return None

    if not isinstance(categories, dict):
        LOGGER.warning(
            "Home Assistant's icon cache has an unexpected structure, "
            "skipping the icons of Spook's actions"
        )
        return None

    return categories.setdefault(ICON_CATEGORY, {})


async def async_inject_service_icons(
    hass: HomeAssistant,
    services: Iterable[tuple[str, str, str]],
    injected: set[tuple[str, str]],
) -> None:
    """Give Spook's actions on other domains the icons Spook has for them.

    `services` holds the domain, the action, and the key it has in Spook's
    services.yaml. An action that already has an icon of its own in Home
    Assistant keeps it. What is put in is added to `injected`, so it can be
    taken out again.
    """
    services = [service for service in services if service[0] != DOMAIN]
    if not services:
        return

    # Loading a domain into the cache replaces whatever the cache held for
    # it, so every domain is loaded first and only then added to.
    domains = {domain for domain, _service, _key in services}
    try:
        spook_icons = (await async_get_icons(hass, ICON_CATEGORY, {DOMAIN})).get(
            DOMAIN, {}
        )
        await async_get_icons(hass, ICON_CATEGORY, domains)
    # pylint: disable-next=broad-exception-caught
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unable to load icons, skipping the icons of Spook's actions")
        return

    if (cache := _async_service_icon_cache(hass)) is None:
        return

    for domain, service, key in services:
        if (icon := spook_icons.get(key)) is None:
            continue

        domain_icons = cache.setdefault(domain, {})
        if service in domain_icons and (domain, service) not in injected:
            continue

        domain_icons[service] = icon
        injected.add((domain, service))


@callback
def async_remove_service_icons(
    hass: HomeAssistant,
    injected: set[tuple[str, str]],
) -> None:
    """Take out the icons Spook put in, and only those."""
    if injected and (cache := _async_service_icon_cache(hass)) is not None:
        for domain, service in injected:
            cache.get(domain, {}).pop(service, None)

    injected.clear()
