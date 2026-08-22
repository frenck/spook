"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.websocket_api.commands import (
    ALL_CONDITION_DESCRIPTIONS_JSON_CACHE,
)
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import callback
from homeassistant.helpers import condition as condition_helper
from homeassistant.helpers.automation import (
    get_absolute_description_key,
    get_relative_description_key,
)
from homeassistant.helpers.condition import (
    CONDITION_DESCRIPTION_CACHE,
    _load_conditions_file,
)
from homeassistant.helpers.translation import (
    async_get_cached_translations,
    async_get_translations,
)
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, LOGGER
from .translation_injection import SpookTranslationInjector

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import Event, HomeAssistant
    from homeassistant.helpers.condition import Condition, ConditionProtocol

# Core calls ``async_get_conditions`` repeatedly (once per config validation
# and per condition instantiation), so the discovery result is cached rather
# than re-globbing and re-importing on every call.
DATA_CONDITIONS: HassKey[dict[str, type[Condition]]] = HassKey("spook_conditions")


async def async_get_conditions(
    hass: HomeAssistant,
) -> dict[str, type[Condition]]:
    """Return the conditions Spook provides.

    Discovered from the leaf modules under ``ectoplasms/*/conditions/``,
    each exposing a ``SpookCondition`` class; keys become ``spook.<key>``.
    """
    if (cached := hass.data.get(DATA_CONDITIONS)) is not None:
        return cached

    conditions: dict[str, type[Condition]] = {}

    def _load_all_condition_modules() -> None:
        """Load all condition modules and collect their conditions."""
        for module_file in Path(__file__).parent.rglob("ectoplasms/*/conditions/*.py"):
            if module_file.name == "__init__.py":
                continue
            module_path = str(module_file.relative_to(Path(__file__).parent))[
                :-3
            ].replace("/", ".")
            module = importlib.import_module(f".{module_path}", __package__)
            conditions[module.SpookCondition.condition] = module.SpookCondition

    await hass.async_add_import_executor_job(_load_all_condition_modules)
    hass.data[DATA_CONDITIONS] = conditions
    return conditions


# Home Assistant resolves a condition to the integration named by the key's
# own prefix: `automation.triggered_by_user` sends it looking for a
# `condition` platform on the automation integration, which does not have
# one. The registration side already knows better, it records Spook as the
# provider, but the lookup side re-derives the platform from the key and
# never consults it (`helpers/condition.py`, `_async_get_condition_platform`).
#
# Actions have no equivalent problem: `hass.services.async_register` writes
# straight into a flat registry, so Spook has been adding actions to other
# integrations' domains for years. Conditions have a resolution step in the
# way, so providing `automation.*` conditions means teaching that step about
# the provider it already recorded.
#
# This patches exactly that one function, and only for keys Spook actually
# provides: everything else is handed to the original untouched. The right
# long-term fix is upstream, having core consult its own provider mapping.
_ORIGINAL_GET_CONDITION_PLATFORM = "_async_get_condition_platform"


async def _async_get_condition_platform(
    hass: HomeAssistant,
    condition_key: str,
    *,
    original: Callable,
) -> tuple[str, ConditionProtocol | None]:
    """Resolve Spook's own conditions, whatever domain they are keyed under."""
    # Ask Spook rather than core's registry, so this does not depend on the
    # order in which platforms happened to be processed.
    conditions = await async_get_conditions(hass)
    if get_relative_description_key(DOMAIN, condition_key) in conditions:
        return DOMAIN, sys.modules[__name__]

    return await original(hass, condition_key)


@callback
def async_setup_foreign_domain_conditions() -> Callable[[], None]:
    """Teach Home Assistant to resolve Spook conditions in other domains.

    Returns a callable that puts the original back. If the function Spook
    patches is not where it used to be, this does nothing and says so, rather
    than taking Spook down with it.
    """
    original = getattr(condition_helper, _ORIGINAL_GET_CONDITION_PLATFORM, None)
    if original is None:
        LOGGER.warning(
            "Home Assistant's condition platform lookup has moved; Spook "
            "conditions outside its own domain will not be available"
        )
        return lambda: None

    async def _patched(
        hass_: HomeAssistant, condition_key: str
    ) -> tuple[str, ConditionProtocol | None]:
        return await _async_get_condition_platform(
            hass_, condition_key, original=original
        )

    setattr(condition_helper, _ORIGINAL_GET_CONDITION_PLATFORM, _patched)

    @callback
    def _restore() -> None:
        """Put Home Assistant's own lookup back, if Spook's is still in place.

        Something else may have wrapped it after Spook did. Restoring blindly
        would throw that away, so leave it alone and let whoever installed it
        clean up after themselves.
        """
        if getattr(condition_helper, _ORIGINAL_GET_CONDITION_PLATFORM, None) is not (
            _patched
        ):
            LOGGER.debug(
                "Home Assistant's condition platform lookup was replaced after "
                "Spook wrapped it; leaving it alone"
            )
            return

        setattr(condition_helper, _ORIGINAL_GET_CONDITION_PLATFORM, original)

    return _restore


CONDITION_TRANSLATION_CATEGORY = "conditions"
GHOST = "👻"


def _foreign_domain(condition_key: str) -> tuple[str, str] | None:
    """Split a Spook condition key that belongs to another integration.

    ``_automation.triggered_by_user`` is Spook's way of saying the absolute
    key is ``automation.triggered_by_user``. Returns the domain and the name
    within it, or None for Spook's own conditions.
    """
    if not condition_key.startswith("_"):
        return None
    domain, _, name = condition_key[1:].partition(".")
    if not name:
        return None
    return domain, name


def condition_schema_key(condition_key: str) -> str:
    """Return the key Spook files a condition's descriptor and strings under.

    Spook keeps both in its own files, so a condition keyed for another
    integration needs a name that survives there and that hassfest accepts,
    which rules out the dot. Same shape the actions already use:
    ``domain_name``, as in ``homeassistant_create_area``.
    """
    if (split := _foreign_domain(condition_key)) is None:
        return condition_key
    domain, name = split
    return f"{domain}_{name}"


@dataclass
class SpookConditionManager:
    """Makes Spook's conditions usable in other integrations' domains.

    Two things stand in the way, and this handles both. Home Assistant
    resolves a condition through the integration named in its key, so the
    lookup needs teaching; and it loads translations per integration, so the
    labels need putting where it will look for them.
    """

    hass: HomeAssistant

    _translations: SpookTranslationInjector = field(init=False)
    _restore_resolution: Callable[[], None] | None = None
    _described: list[str] = field(default_factory=list)
    _condition_schemas: dict[str, Any] = field(default_factory=dict)
    _translation_listener: Callable[[], None] | None = None

    def __post_init__(self) -> None:
        """Post initialization."""
        self._translations = SpookTranslationInjector(
            self.hass,
            CONDITION_TRANSLATION_CATEGORY,
            "condition",
        )

    async def async_setup(self) -> None:
        """Set up Spook's conditions."""
        LOGGER.debug("Setting up Spook conditions")

        integration = await async_get_integration(self.hass, DOMAIN)
        self._condition_schemas = cast(
            "dict[str, Any]",
            await self.hass.async_add_executor_job(
                _load_conditions_file,
                integration,
            ),
        )

        self._restore_resolution = async_setup_foreign_domain_conditions()
        await self.async_inject_condition_descriptions()
        await self.async_inject_condition_translations()
        self._translation_listener = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE,
            self._async_core_config_updated,
        )

    async def async_inject_condition_translations(self) -> None:
        """Put Spook's condition strings under the domains they are keyed to."""
        conditions = await async_get_conditions(self.hass)
        foreign = {
            key: split
            for key in conditions
            if (split := _foreign_domain(key)) is not None
        }
        if not foreign:
            return

        language = self.hass.config.language
        domains = {domain for domain, _ in foreign.values()}
        await async_get_translations(
            self.hass,
            language,
            CONDITION_TRANSLATION_CATEGORY,
            {DOMAIN, *domains},
        )
        spook_strings = async_get_cached_translations(
            self.hass,
            language,
            CONDITION_TRANSLATION_CATEGORY,
            DOMAIN,
        )

        for domain, name in foreign.values():
            spook_key = condition_schema_key(f"_{domain}.{name}")
            spook_prefix = (
                f"component.{DOMAIN}.{CONDITION_TRANSLATION_CATEGORY}.{spook_key}."
            )
            target_prefix = (
                f"component.{domain}.{CONDITION_TRANSLATION_CATEGORY}.{name}."
            )
            self._translations.inject(
                language,
                domain,
                {
                    f"{target_prefix}{key.removeprefix(spook_prefix)}": (
                        f"{value} {GHOST}"
                        if key == f"{spook_prefix}name" and GHOST not in value
                        else value
                    )
                    for key, value in spook_strings.items()
                    if key.startswith(spook_prefix)
                },
            )

    async def async_inject_condition_descriptions(self) -> None:
        """Put the descriptors for foreign-domain conditions where core keeps them.

        Home Assistant files a descriptor under the key it reads from
        `conditions.yaml`, prefixed with the integration that owns the file.
        For `automation_triggered_by_user` that gives `spook.…`, which is not
        the key the condition is registered under, so core never finds it.

        Without a descriptor a condition still works but vanishes from the
        editor: the websocket drops every condition whose description is None
        (`websocket_api/commands.py`), so it becomes YAML-only and
        undiscoverable.

        Writing into the cache is enough, because `async_get_all_descriptions`
        only fills in the keys it finds missing and copies the rest through.
        """
        conditions = await async_get_conditions(self.hass)
        foreign = [key for key in conditions if _foreign_domain(key) is not None]
        if not foreign:
            return

        cache = self.hass.data.get(CONDITION_DESCRIPTION_CACHE)
        if cache is None:
            LOGGER.warning(
                "Home Assistant's condition description cache is not there; "
                "Spook conditions outside its own domain will not show up in "
                "the automation editor"
            )
            return

        for key in foreign:
            schema = self._condition_schemas.get(condition_schema_key(key)) or {}
            described: dict[str, Any] = {"fields": schema.get("fields", {})}
            if (target := schema.get("target")) is not None:
                described["target"] = target

            absolute = get_absolute_description_key(DOMAIN, key)
            cache[absolute] = described
            self._described.append(absolute)

        # The websocket serves a pre-rendered payload and only rebuilds it when
        # the description set changes identity, so it has to be dropped by hand.
        self.hass.data.pop(ALL_CONDITION_DESCRIPTIONS_JSON_CACHE, None)

    async def _async_core_config_updated(self, event: Event) -> None:
        """Re-inject condition translations when the language changes."""
        if "language" not in event.data:
            return
        await self.async_inject_condition_translations()

    @callback
    def async_on_unload(self) -> None:
        """Tear down Spook's conditions."""
        LOGGER.debug("Tearing down Spook conditions")
        if self._translation_listener:
            self._translation_listener()
            self._translation_listener = None

        if self._restore_resolution:
            self._restore_resolution()
            self._restore_resolution = None

        if cache := self.hass.data.get(CONDITION_DESCRIPTION_CACHE):
            for key in self._described:
                cache.pop(key, None)
            self.hass.data.pop(ALL_CONDITION_DESCRIPTIONS_JSON_CACHE, None)
        self._described.clear()

        self._translations.restore()
