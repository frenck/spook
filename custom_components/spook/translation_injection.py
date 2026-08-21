"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.translation import (
    _async_get_translations_cache,
    async_get_cached_translations,
)

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@dataclass
class SpookTranslationInjector:
    """Puts Spook's own strings where Home Assistant will look for them.

    Spook adds things to other integrations' domains: actions on `person`,
    conditions on `automation`. Home Assistant loads translations per
    integration, so it looks for those strings under the domain of the thing
    rather than under Spook, and never finds them.

    This writes them into Home Assistant's translation cache under the domain
    that will be asked for, remembering whatever was there so unloading Spook
    puts it back. Reaching into that cache means touching a private helper, so
    every access is guarded: if the structure changes, Spook logs it and skips
    the labels rather than failing to load.
    """

    hass: HomeAssistant
    category: str
    subject: str

    _overrides: dict[tuple[str, str, str], str | None] = field(default_factory=dict)

    @callback
    def component_cache(
        self,
        language: str,
        domain: str,
        *,
        create: bool = False,
    ) -> dict[str, str] | None:
        """Return Home Assistant's translation cache for one component."""
        translations_cache = _async_get_translations_cache(self.hass)

        try:
            cache = translations_cache.cache_data.cache
        except AttributeError:
            LOGGER.warning(
                "Unable to access Home Assistant's translation cache, "
                "skipping Spook %s translation update",
                self.subject,
            )
            return None

        if not isinstance(cache, dict):
            LOGGER.warning(
                "Home Assistant's translation cache has an unexpected structure, "
                "skipping Spook %s translation update",
                self.subject,
            )
            return None

        if create:
            return (
                cache.setdefault(language, {})
                .setdefault(self.category, {})
                .setdefault(domain, {})
            )

        return cache.get(language, {}).get(self.category, {}).get(domain)

    @callback
    def inject(self, language: str, domain: str, strings: dict[str, str]) -> None:
        """Write strings into a component's cache, remembering what was there."""
        component_cache = self.component_cache(language, domain, create=True)
        if component_cache is None:
            return

        existing = async_get_cached_translations(
            self.hass,
            language,
            self.category,
            domain,
        )

        for key, value in strings.items():
            # A string already equal to the one going in is Spook's own, from
            # an earlier injection: a language change, a reload, or a cache
            # that outlived the instance that wrote it. Remembering it as the
            # original is how Spook's text ends up permanently baked into
            # another integration's translations.
            original = existing.get(key)
            if original == value:
                original = None

            self._overrides.setdefault((language, domain, key), original)
            component_cache[key] = value

    @callback
    def restore(self) -> None:
        """Put back every string Spook overwrote."""
        for (language, domain, key), original in self._overrides.items():
            component_cache = self.component_cache(language, domain)
            if component_cache is None:
                continue

            if original is None:
                component_cache.pop(key, None)
            else:
                component_cache[key] = original

        self._overrides.clear()
