"""Spook - Your homie. Spook's own themes, in the theme picker without YAML."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.components.frontend import DEFAULT_THEME
from homeassistant.const import EVENT_THEMES_UPDATED
from homeassistant.core import callback
from homeassistant.util.yaml import load_yaml_dict

from ..const import LOGGER
from ..core_compat import (
    async_get_default_themes,
    async_get_themes,
    async_load_stored_default_themes,
    async_set_default_themes,
)

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

# Each file here is written the way a file in somebody's own `themes` folder
# is: the theme's name at the top, its variables below. One can be copied
# over as it is, and core's own theme schema checks them in the tests.
THEMES_PATH = Path(__file__).parent


def load_themes() -> dict[str, dict[str, Any]]:
    """Load the themes Spook brings, by name. Does I/O."""
    themes: dict[str, dict[str, Any]] = {}
    for path in sorted(THEMES_PATH.glob("*.yaml")):
        themes.update(load_yaml_dict(str(path)))

    return themes


async def async_setup_themes(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Put Spook's themes in the theme picker, and keep them there.

    Returns the callback that takes them out again.
    """
    if async_get_themes(hass) is None:
        LOGGER.debug("No frontend to bring themes to, leaving them out")
        return lambda: None

    themes = await hass.async_add_executor_job(load_themes)
    stored_light, stored_dark = await async_load_stored_default_themes(hass)

    delivery = _ThemeDelivery(hass, themes)
    return delivery.async_start(stored_light, stored_dark)


# pylint: disable-next=too-few-public-methods
class _ThemeDelivery:
    """Spook's themes, put in the frontend's list and put back when it loses them.

    The list is rebuilt from YAML on every `frontend.reload_themes`, which
    the Marketplace calls after each theme it installs, updates or removes.
    So losing them is a normal thing, not a rare one. A default theme that
    was one of Spook's is reset to the frontend's own look on the way, and
    at startup too, because the list is filled from YAML before Spook is
    there. That goes back with them.
    """

    def __init__(self, hass: HomeAssistant, themes: dict[str, dict[str, Any]]) -> None:
        """Initialize the delivery."""
        self._hass = hass
        self._themes = themes

        # The defaults that were one of Spook's themes the last time they
        # were all there. What the frontend holds when they are not is no
        # guide: it has reset them by then.
        self._default_light: str | None = None
        self._default_dark: str | None = None

    @callback
    def async_start(
        self, stored_light: str | None, stored_dark: str | None
    ) -> CALLBACK_TYPE:
        """Deliver the themes, then keep an eye on them.

        Takes the defaults the frontend stored, which at startup still name
        a theme of Spook's that the frontend just dropped.
        """
        self._async_remember_defaults(stored_light, stored_dark)
        stop_listening = self._hass.bus.async_listen(
            EVENT_THEMES_UPDATED, self._async_themes_updated
        )
        self._async_deliver()

        @callback
        def _async_stop() -> None:
            """Stop putting the themes back, and take them out."""
            stop_listening()
            self._async_take_back()

        return _async_stop

    @callback
    def _async_remember_defaults(self, light: str | None, dark: str | None) -> None:
        """Remember which of the defaults are Spook's themes."""
        self._default_light = light if light in self._themes else None
        self._default_dark = dark if dark in self._themes else None

    @callback
    def _async_themes_updated(self, _: Event) -> None:
        """Put the themes back if they are gone, or note the defaults if not.

        Spook's own delivery fires this event too, and finds them all there
        the second time round. That is what keeps this from going in circles.
        """
        if (themes := async_get_themes(self._hass)) is None:
            return

        if all(name in themes for name in self._themes):
            self._async_remember_defaults(*async_get_default_themes(self._hass))
            return

        LOGGER.debug("The frontend lost Spook's themes, putting them back")
        self._async_deliver()

    @callback
    def _async_deliver(self) -> None:
        """Put the themes in the list, with any default that was one of them."""
        if (themes := async_get_themes(self._hass)) is None:
            return

        # A theme of somebody's own by the same name wins. It is theirs, in
        # their configuration, and taking it over would be a surprise.
        for name, theme in self._themes.items():
            themes.setdefault(name, theme)

        # Only a default the frontend reset gets put back. One that names
        # some other theme was picked since, and stays.
        light, dark = async_get_default_themes(self._hass)
        if light == DEFAULT_THEME and self._default_light:
            light = self._default_light
        if dark is None and self._default_dark:
            dark = self._default_dark
        async_set_default_themes(self._hass, light, dark)

        self._hass.bus.async_fire(EVENT_THEMES_UPDATED)

    @callback
    def _async_take_back(self) -> None:
        """Take the themes out of the list, on Spook's way out.

        A default that names one of them goes back to the frontend's own
        look, in memory: the frontend reads the default theme from the list
        when it is set again, and fails on one that is not there. The
        stored default stays, so Spook loaded again picks it up.
        """
        if (themes := async_get_themes(self._hass)) is None:
            return

        taken = {
            name for name, theme in self._themes.items() if themes.get(name) is theme
        }
        if not taken:
            return

        for name in taken:
            del themes[name]

        light, dark = async_get_default_themes(self._hass)
        async_set_default_themes(
            self._hass,
            DEFAULT_THEME if light in taken else light,
            None if dark in taken else dark,
        )

        self._hass.bus.async_fire(EVENT_THEMES_UPDATED)
