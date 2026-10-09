"""Spook - Your homie."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar, final

import voluptuous as vol

from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_CORE_CONFIG_UPDATE
from homeassistant.core import (
    Event,
    HomeAssistant,
    Service,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM
from homeassistant.helpers.service import (
    SERVICE_DESCRIPTION_CACHE,
    async_register_admin_service,
    async_set_service_schema,
)
from homeassistant.helpers.translation import (
    _async_get_translations_cache,
    async_get_cached_translations,
    async_get_translations,
)
from homeassistant.loader import async_get_integration
from homeassistant.setup import ATTR_COMPONENT

from .const import DOMAIN, LOGGER
from .core_compat import load_service_descriptions
from .service_icons import async_inject_service_icons, async_remove_service_icons

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from types import ModuleType


_EntityT = TypeVar("_EntityT", bound=Entity, default=Entity)
GHOST = "👻"
SERVICE_TRANSLATION_CATEGORY = "services"
SELECTOR_TRANSLATION_CATEGORY = "selector"


class AbstractSpookServiceBase(ABC):
    """Abstract base class to hold a Spook service."""

    hass: HomeAssistant
    domain: str
    service: str
    schema: dict[str | vol.Marker, Any] | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service."""
        self.hass = hass

    @abstractmethod
    @callback
    def async_register(self) -> bool:
        """Register the service with Home Assistant.

        Returns True when the service was actually registered.
        """
        raise NotImplementedError

    @final
    @callback
    def async_unregister(self) -> None:
        """Unregister the service from Home Assistant."""
        LOGGER.debug(
            "Unregistering Spook service: %s.%s",
            self.domain,
            self.service,
        )

        self.hass.services.async_remove(self.domain, self.service)


class ReplaceExistingService(AbstractSpookServiceBase):
    """Service replaces/may replace an existing service."""

    overriden_service: Service | None = None


class AbstractSpookService(AbstractSpookServiceBase):
    """Abstract class to hold a Spook service."""

    supports_response: SupportsResponse = SupportsResponse.NONE

    @final
    @callback
    def async_register(self) -> bool:
        """Register the service with Home Assistant."""
        # Only register the service if the domain is the spook integration
        # or if the target integration is loaded.
        if self.domain != DOMAIN and self.domain not in self.hass.config.components:
            LOGGER.debug(
                "Not registering Spook %s.%s service, %s is not loaded",
                self.domain,
                self.service,
                self.domain,
            )
            return False

        LOGGER.debug(
            "Registering Spook service: %s.%s",
            self.domain,
            self.service,
        )

        self.hass.services.async_register(
            domain=self.domain,
            service=self.service,
            service_func=self.async_handle_service,
            schema=vol.Schema(self.schema) if self.schema else None,
            supports_response=self.supports_response,
        )

        return True

    @abstractmethod
    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        raise NotImplementedError


class AbstractSpookAdminService(AbstractSpookServiceBase):
    """Abstract class to hold a Spook admin service."""

    supports_response: SupportsResponse = SupportsResponse.NONE

    @final
    @callback
    def async_register(self) -> bool:
        """Register the service with Home Assistant."""
        if self.domain != DOMAIN and self.domain not in self.hass.config.components:
            LOGGER.debug(
                "Not registering Spook %s.%s admin service, %s is not loaded",
                self.domain,
                self.service,
                self.domain,
            )
            return False

        LOGGER.debug(
            "Registering Spook admin service: %s.%s",
            self.domain,
            self.service,
        )
        async_register_admin_service(
            hass=self.hass,
            domain=self.domain,
            service=self.service,
            service_func=self.async_handle_service,
            schema=vol.Schema(self.schema) if self.schema else None,
            supports_response=self.supports_response,
        )

        return True

    @abstractmethod
    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        raise NotImplementedError


class AbstractSpookEntityService(AbstractSpookServiceBase, Generic[_EntityT]):
    """Abstract class to hold a Spook entity service."""

    platform: str
    required_features: list[int] | None = None
    supports_response: SupportsResponse = SupportsResponse.NONE

    @final
    @callback
    def async_register(self) -> bool:
        """Register the service with Home Assistant."""
        LOGGER.debug(
            "Registering Spook entity service: %s.%s for platform %s",
            self.domain,
            self.service,
            self.platform,
        )

        if not (
            platform := next(
                (
                    platform
                    for platform in self.hass.data.get(DATA_ENTITY_PLATFORM, {}).get(
                        self.domain, []
                    )
                    if platform.domain == self.platform
                ),
                None,
            )
        ):
            msg = (
                f"Could not find platform {self.platform} for domain "
                f"{self.domain} to register service: "
                f"{self.domain}.{self.service}"
            )
            raise RuntimeError(msg)

        platform.async_register_entity_service(
            name=self.service,
            func=self.async_handle_service,
            schema=self.schema,
            required_features=self.required_features,
            supports_response=self.supports_response,
        )

        return True

    @abstractmethod
    async def async_handle_service(
        self,
        entity: _EntityT,
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle the service call."""
        raise NotImplementedError


class AbstractSpookEntityComponentService(AbstractSpookServiceBase, Generic[_EntityT]):
    """Abstract class to hold a Spook entity component service."""

    required_features: list[int] | None = None
    supports_response: SupportsResponse = SupportsResponse.NONE
    #: For an action that changes how something is set up rather than what it
    #: is doing, which Home Assistant keeps to admins. Automations still pass.
    admin_only: bool = False

    @final
    @callback
    def async_register(self) -> bool:
        """Register the service with Home Assistant."""
        LOGGER.debug(
            "Registering Spook entity component service: %s.%s",
            self.domain,
            self.service,
        )

        # Not every component is there when Spook is. Home Assistant loads
        # calendar and todo only once an integration brings a calendar or a
        # to-do list along, which can be well after Spook, or never. The
        # manager waits for it and registers the action then.
        if self.domain not in self.hass.data.get(DATA_INSTANCES, {}):
            LOGGER.debug(
                "Not registering Spook %s.%s service yet, %s is not loaded",
                self.domain,
                self.service,
                self.domain,
            )
            return False

        component: EntityComponent[Entity] = self.hass.data[DATA_INSTANCES][self.domain]

        component.async_register_entity_service(
            name=self.service,
            func=(
                self._async_handle_service_as_admin
                if self.admin_only
                else self.async_handle_service
            ),
            schema=self.schema,
            required_features=self.required_features,
            supports_response=self.supports_response,
        )

        return True

    async def _async_handle_service_as_admin(
        self,
        entity: _EntityT,
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle the call, if whoever made it may change how things are set up.

        The same check Home Assistant does for an admin-only entity action. It
        is done here rather than asked of Home Assistant, because the option
        to ask arrived in a later version than the oldest one Spook runs on,
        and passing it there fails registering every one of these actions.
        """
        if call.context.user_id:
            user = await self.hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
            if not user.is_admin:
                raise Unauthorized(context=call.context)

        return await self.async_handle_service(entity, call)

    @abstractmethod
    async def async_handle_service(
        self,
        entity: _EntityT,
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle the service call."""
        raise NotImplementedError


# Most of these track something it put into Home Assistant, to undo on unload.
@dataclass
class SpookServiceManager:  # pylint: disable=too-many-instance-attributes
    """Class to manage Spook services."""

    hass: HomeAssistant

    _services: set[AbstractSpookService] = field(default_factory=set)
    _service_schemas: dict[str, Any] = field(default_factory=dict)
    _service_translation_overrides: dict[tuple[str, str, str], str | None] = field(
        default_factory=dict
    )
    # The same, for the option labels of the selectors those actions use.
    _selector_translation_overrides: dict[tuple[str, str, str], str | None] = field(
        default_factory=dict
    )
    # The icons Spook gave its actions on other domains, as (domain, action).
    _injected_service_icons: set[tuple[str, str]] = field(default_factory=set)
    # Services for a domain that was not loaded yet, by that domain.
    _waiting_for_domain: dict[str, list[AbstractSpookService]] = field(
        default_factory=dict
    )
    # Everything to undo on unload: the listeners, and any translation
    # injection still on its way.
    _on_unload: list[Callable[[], None]] = field(default_factory=list)
    # The languages Spook's strings went into. Not just the server's: every
    # person picks their own in their profile, and the frontend asks for that
    # one. #1820.
    _languages: set[str] = field(default_factory=set)
    # A language whose injection is on its way, so a second request for it
    # waits for that one instead of reading the cache halfway.
    _language_tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    _starting_languages: set[str] = field(default_factory=set)
    # Whether Home Assistant's translation loading is still being followed.
    # Turned off the moment unloading starts, for a load already under way.
    follows_translation_loads: bool = False

    def __post_init__(self) -> None:
        """Post initialization."""
        LOGGER.debug("Spook service manager initialized")

    async def async_setup(self) -> None:
        """Set up the Spook services."""
        LOGGER.debug("Setting up Spook services")

        # Load service schemas
        integration = await async_get_integration(self.hass, DOMAIN)
        self._service_schemas = await self.hass.async_add_executor_job(
            load_service_descriptions,
            integration,
        )

        modules: list[ModuleType] = []

        def _load_all_service_modules() -> None:
            """Load all service modules."""
            for module_file in Path(__file__).parent.rglob(
                "ectoplasms/*/services/*.py"
            ):
                if module_file.name == "__init__.py":
                    continue
                module_path = str(module_file.relative_to(Path(__file__).parent))[
                    :-3
                ].replace("/", ".")
                modules.append(importlib.import_module(f".{module_path}", __package__))

        await self.hass.async_add_import_executor_job(_load_all_service_modules)

        # Listening starts before anything is parked, and nothing between here
        # and the end of the loop below waits on anything. A domain that loads
        # in the meantime is either there for the loop to register straight
        # away, or loads afterwards with the listener already in place.
        self._on_unload = [
            self.hass.bus.async_listen(
                EVENT_COMPONENT_LOADED,
                self._async_component_loaded,
            ),
            self.hass.bus.async_listen(
                EVENT_CORE_CONFIG_UPDATE,
                self._async_core_config_updated,
            ),
        ]

        for module in modules:
            self._async_setup_service_module(module)

        self._async_follow_translation_loads()
        await self.async_inject_service_translations()

    @callback
    def _async_follow_translation_loads(self) -> None:
        """Inject into every language Home Assistant loads, as it loads it.

        Home Assistant loads a language the moment somebody asks for it, and
        says nothing when it does. Spook's strings for a domain that is not
        its own have to be written into that language by hand, so it follows
        the loading on this one cache: once a language is in for the first
        time, Spook's strings go in too, before the caller reads them.

        The cache keeps its attributes in slots, so its method cannot be
        swapped on the instance. Its class can, for a subclass that adds no
        slots of its own, and only this Home Assistant's cache is touched.
        """
        translations_cache = _async_get_translations_cache(self.hass)
        original_class = type(translations_cache)
        if not callable(getattr(original_class, "async_load", None)):
            LOGGER.warning(
                "Unable to follow Home Assistant's translation loading, "
                "Spook's actions are only translated in the server's language"
            )
            return

        manager = self

        class _FollowedTranslationCache(original_class):  # type: ignore[misc,valid-type]
            """Home Assistant's translation cache, with Spook along."""

            __slots__ = ()

            async def async_load(self, language: str, components: set[str]) -> None:
                """Load as ever, then add Spook's strings to a new language."""
                await super().async_load(language, components)
                # Unloading can have happened while that waited on the lock.
                if manager.follows_translation_loads:
                    await manager.async_follow_language(language)

        try:
            translations_cache.__class__ = _FollowedTranslationCache
        except TypeError:
            LOGGER.warning(
                "Unable to follow Home Assistant's translation loading, "
                "Spook's actions are only translated in the server's language"
            )
            return

        self.follows_translation_loads = True

        @callback
        def _stop_following() -> None:
            self.follows_translation_loads = False
            # Only when nothing swapped it again since.
            if translations_cache.__class__ is _FollowedTranslationCache:
                translations_cache.__class__ = original_class

        self._on_unload.append(_stop_following)

    async def async_follow_language(self, language: str) -> None:
        """Translate Spook's actions into a language loaded for the first time.

        One injection per language, which every request for that language
        waits for. Only one that went through marks the language as done; a
        failed or cancelled one is tried again by the next request.
        """
        if language in self._languages or language in self._starting_languages:
            return

        task = self._language_tasks.get(language)
        if task is None or task.done():
            # A finished one is still listed until its callback has run; one
            # that failed is not a reason to stop trying.
            task = self._async_start_language_task(language)
        elif task is asyncio.current_task():
            # The injection itself loading this language again.
            return

        try:
            # Shielded: one caller being cancelled must not cancel the
            # injection the others are waiting for.
            await asyncio.shield(task)
        except asyncio.CancelledError:
            # Only swallowed when unloading cancelled Spook's part; the caller
            # being cancelled itself goes on as it should.
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise
        # pylint: disable-next=broad-exception-caught
        except Exception:  # noqa: BLE001, S110
            # Logged once, where the task finishes. The caller only asked for
            # translations, and Spook's part going wrong must not take theirs
            # with it.
            pass

    @callback
    def _async_start_language_task(self, language: str) -> asyncio.Task[None]:
        """Start injecting into a language, in a task unloading cancels."""
        # Home Assistant starts a task eagerly: the injection runs, and loads
        # this language again, before the task is handed back to be listed.
        self._starting_languages.add(language)
        try:
            task = self.hass.async_create_task(
                self.async_inject_service_translations([language]),
                f"Inject Spook service translations in {language}",
            )
        finally:
            self._starting_languages.discard(language)
        self._language_tasks[language] = task
        self._on_unload.append(task.cancel)

        @callback
        def _finished(_task: asyncio.Task[None]) -> None:
            self._language_tasks.pop(language, None)
            if task.cancel in self._on_unload:
                self._on_unload.remove(task.cancel)
            if task.cancelled():
                return
            if (err := task.exception()) is not None:
                LOGGER.error(
                    "Spook could not translate its actions into %s: %s",
                    language,
                    err,
                )
                return
            self._languages.add(language)

        task.add_done_callback(_finished)
        return task

    @callback
    def _async_setup_service_module(self, module: ModuleType) -> None:
        """Set up a single service module, isolating failures.

        A service that fails to set up must not prevent the rest of Spook
        from loading.
        """
        try:
            service = module.SpookService(self.hass)
        # pylint: disable-next=broad-exception-caught
        except Exception:  # noqa: BLE001
            LOGGER.exception(
                "Spook service %s failed to set up and has been skipped; "
                "please report this issue at "
                "https://github.com/frenck/spook/issues",
                module.__name__,
            )
            return

        self._async_setup_service(service, module.__name__)

    @callback
    def _async_setup_service(self, service: AbstractSpookService, name: str) -> None:
        """Register one service, isolating failures.

        One for a domain that is not loaded yet waits for it, and is set up
        through here again once it is.
        """
        try:
            if isinstance(
                service,
                ReplaceExistingService,
            ) and self.hass.services.has_service(service.domain, service.service):
                LOGGER.debug(
                    "Unregistering service that will be overriden service: %s.%s",
                    service.domain,
                    service.service,
                )
                # pylint: disable=protected-access
                service.overriden_service = (
                    self.hass.services._services[service.domain]  # noqa: SLF001
                ).pop(service.service)

            if not self.async_register_service(service):
                self._waiting_for_domain.setdefault(service.domain, []).append(service)
        # pylint: disable-next=broad-exception-caught
        except Exception:  # noqa: BLE001
            # If the service this one overrides was already unregistered,
            # restore it; a failing setup must not silently remove a core
            # service until the next restart.
            if (
                isinstance(service, ReplaceExistingService)
                and service.overriden_service is not None
            ):
                # pylint: disable-next=protected-access
                self.hass.services._services.setdefault(  # noqa: SLF001
                    service.domain,
                    {},
                )[service.service] = service.overriden_service
            LOGGER.exception(
                "Spook service %s failed to set up and has been skipped; "
                "please report this issue at "
                "https://github.com/frenck/spook/issues",
                name,
            )

    @callback
    def _async_component_loaded(self, event: Event) -> None:
        """Register the services that were waiting for this domain."""
        if not (
            waiting := self._waiting_for_domain.pop(event.data[ATTR_COMPONENT], [])
        ):
            return

        for service in waiting:
            self._async_setup_service(service, type(service).__module__)

        # The descriptions went in with the registration, the translations and
        # icons did not: those are injected for every registered service in one
        # go.
        self._async_reinject_service_translations()

    @callback
    def _async_reinject_service_translations(
        self, languages: Iterable[str] | None = None
    ) -> None:
        """Inject the translations again, in a task unloading cancels.

        Injecting waits on loading translations before it writes anything.
        Left running through an unload, it would write Spook's strings back
        for actions that were just taken away, after unload put the originals
        back.
        """
        task = self.hass.async_create_task(
            self.async_inject_service_translations(languages),
            "Inject Spook service translations",
        )
        self._on_unload.append(task.cancel)

        @callback
        def _finished(_task: asyncio.Task[None]) -> None:
            # Already gone when unloading cleared the list and cancelled it.
            if task.cancel in self._on_unload:
                self._on_unload.remove(task.cancel)

        task.add_done_callback(_finished)

    @callback
    def async_register_service(self, service: AbstractSpookService) -> bool:
        """Register a Spook service.

        Returns False when the domain it belongs to is not loaded (yet).
        """
        # A service aimed at an integration that is not set up never lands in
        # Home Assistant. Injecting a description for it would then describe
        # an action that does not exist, which core refuses with a KeyError.
        if not service.async_register():
            return False

        self._services.add(service)

        # Override service description with Spook's if the service is not
        # for the Spook integration.
        if service.domain != DOMAIN and (
            service_schema := self._service_schemas.get(
                f"{service.domain}_{service.service}",
            )
        ):
            LOGGER.debug(
                "Injecting Spook service schema for: %s.%s",
                service.domain,
                service.service,
            )
            async_set_service_schema(
                self.hass,
                domain=service.domain,
                service=service.service,
                schema=service_schema,
            )

        return True

    @callback
    def _service_schema_key(self, service: AbstractSpookService) -> str:
        """Return the services.yaml key for a Spook service."""
        if service.domain == DOMAIN:
            return service.service
        return f"{service.domain}_{service.service}"

    @callback
    def _service_translation_strings(
        self,
        service: AbstractSpookService,
        cached_spook_translations: dict[str, str],
    ) -> dict[str, str]:
        """Return service translation strings mapped to the target domain."""
        schema_key = self._service_schema_key(service)
        spook_prefix = f"component.{DOMAIN}.services.{schema_key}."
        target_prefix = f"component.{service.domain}.services.{service.service}."

        return {
            f"{target_prefix}{key.removeprefix(spook_prefix)}": (
                f"{value} {GHOST}"
                if key == f"{spook_prefix}name" and GHOST not in value
                else value
            )
            for key, value in cached_spook_translations.items()
            if key.startswith(spook_prefix)
        }

    @callback
    def _translation_component_cache(
        self,
        language: str,
        domain: str,
        *,
        create: bool = False,
        category: str = SERVICE_TRANSLATION_CATEGORY,
    ) -> dict[str, str] | None:
        """Return the Home Assistant translation cache for a component."""
        translations_cache = _async_get_translations_cache(self.hass)

        try:
            cache = translations_cache.cache_data.cache
        except AttributeError:
            LOGGER.warning(
                "Unable to access Home Assistant's translation cache, "
                "skipping Spook service translation update"
            )
            return None

        if not isinstance(cache, dict):
            LOGGER.warning(
                "Home Assistant's translation cache has an unexpected structure, "
                "skipping Spook service translation update"
            )
            return None

        if create:
            return (
                cache.setdefault(language, {})
                .setdefault(category, {})
                .setdefault(domain, {})
            )

        return cache.get(language, {}).get(category, {}).get(domain)

    @callback
    def _inject_service_translation_strings(
        self,
        service: AbstractSpookService,
        cached_spook_translations: dict[str, str],
        language: str,
    ) -> None:
        """Inject service translation strings into Home Assistant's cache."""
        component_cache = self._translation_component_cache(
            language,
            service.domain,
            create=True,
        )
        if component_cache is None:
            return

        cached_translations = async_get_cached_translations(
            self.hass,
            language,
            SERVICE_TRANSLATION_CATEGORY,
            service.domain,
        )

        for key, value in self._service_translation_strings(
            service,
            cached_spook_translations,
        ).items():
            self._service_translation_overrides.setdefault(
                (language, service.domain, key), cached_translations.get(key)
            )
            component_cache[key] = value

    @callback
    def _selector_translation_keys(self, service: AbstractSpookService) -> set[str]:
        """Return the selector translation keys a Spook service's fields use."""
        schema = self._service_schemas.get(self._service_schema_key(service)) or {}
        keys: set[str] = set()
        for field_schema in (schema.get("fields") or {}).values():
            for selector_config in (
                (field_schema or {}).get("selector") or {}
            ).values():
                if isinstance(selector_config, dict) and (
                    key := selector_config.get("translation_key")
                ):
                    keys.add(key)
        return keys

    @callback
    def _inject_selector_translation_strings(
        self,
        service: AbstractSpookService,
        cached_spook_translations: dict[str, str],
        language: str,
    ) -> None:
        """Inject the option labels of a Spook service's selectors.

        Home Assistant looks a selector's labels up under the domain the action
        belongs to, `component.todo.selector...` for a `todo` action, and Spook
        keeps them under its own. Without this, the options show as their raw
        values.
        """
        if not (keys := self._selector_translation_keys(service)):
            return

        component_cache = self._translation_component_cache(
            language,
            service.domain,
            create=True,
            category=SELECTOR_TRANSLATION_CATEGORY,
        )
        if component_cache is None:
            return

        cached_translations = async_get_cached_translations(
            self.hass,
            language,
            SELECTOR_TRANSLATION_CATEGORY,
            service.domain,
        )

        for key in keys:
            spook_prefix = f"component.{DOMAIN}.selector.{key}."
            target_prefix = f"component.{service.domain}.selector.{key}."
            for spook_key, value in cached_spook_translations.items():
                if not spook_key.startswith(spook_prefix):
                    continue
                target_key = f"{target_prefix}{spook_key.removeprefix(spook_prefix)}"
                self._selector_translation_overrides.setdefault(
                    (language, service.domain, target_key),
                    cached_translations.get(target_key),
                )
                component_cache[target_key] = value

    async def async_inject_service_translations(
        self, languages: Iterable[str] | None = None
    ) -> None:
        """Inject Spook service strings and icons into Home Assistant.

        Into the languages given, or every language Spook has written into.
        """
        services = [
            service
            for service in self._services
            if self._service_schema_key(service) in self._service_schemas
        ]

        if not services:
            return

        if languages is None:
            # The server's own is always one of them.
            self._languages.add(self.hass.config.language)
            languages = self._languages

        domains = {DOMAIN, *(service.domain for service in services)}
        for language in list(languages):
            await self._async_inject_translations_for(language, services, domains)

        await async_inject_service_icons(
            self.hass,
            (
                (service.domain, service.service, self._service_schema_key(service))
                for service in services
            ),
            self._injected_service_icons,
        )

    async def _async_inject_translations_for(
        self,
        language: str,
        services: list[AbstractSpookService],
        domains: set[str],
    ) -> None:
        """Inject the strings and selector labels of these services in a language."""
        await async_get_translations(
            self.hass, language, SERVICE_TRANSLATION_CATEGORY, domains
        )
        cached_spook_translations = async_get_cached_translations(
            self.hass, language, SERVICE_TRANSLATION_CATEGORY, DOMAIN
        )
        for service in services:
            self._inject_service_translation_strings(
                service, cached_spook_translations, language
            )

        await async_get_translations(
            self.hass, language, SELECTOR_TRANSLATION_CATEGORY, domains
        )
        cached_spook_selector_translations = async_get_cached_translations(
            self.hass, language, SELECTOR_TRANSLATION_CATEGORY, DOMAIN
        )
        for service in services:
            self._inject_selector_translation_strings(
                service, cached_spook_selector_translations, language
            )

    @callback
    def _async_core_config_updated(self, event: Event) -> None:
        """Re-inject service translations when the language changes."""
        if "language" not in event.data:
            return

        # The language it was is kept: somebody can still have it as theirs.
        self._languages.add(self.hass.config.language)
        self._async_reinject_service_translations([self.hass.config.language])

    @callback
    def async_clear_service_translation_overrides(self) -> None:
        """Restore translation strings that were overridden by Spook."""
        self._restore(self._service_translation_overrides, SERVICE_TRANSLATION_CATEGORY)
        self._restore(
            self._selector_translation_overrides, SELECTOR_TRANSLATION_CATEGORY
        )

    @callback
    def _restore(
        self,
        overrides: dict[tuple[str, str, str], str | None],
        category: str,
    ) -> None:
        """Put back what Spook overrode, and take away what it only added."""
        for (language, domain, key), original_value in overrides.items():
            component_cache = self._translation_component_cache(
                language, domain, category=category
            )
            if component_cache is None:
                continue

            if original_value is None:
                component_cache.pop(key, None)
            else:
                component_cache[key] = original_value

        overrides.clear()

    @callback
    def async_on_unload(self) -> None:
        """Tear down the Spook services."""
        LOGGER.debug("Tearing down Spook services")
        # A copy, as cancelling a finished injection takes it off the list.
        for undo in list(self._on_unload):
            undo()
        self._on_unload.clear()
        self._waiting_for_domain.clear()

        for service in self._services:
            LOGGER.debug(
                "Unregistering service: %s.%s",
                service.domain,
                service.service,
            )
            service.async_unregister()

            if (
                isinstance(service, ReplaceExistingService)
                and service.overriden_service
            ):
                LOGGER.debug(
                    "Restoring service that was overriden previously: %s.%s",
                    service.domain,
                    service.service,
                )

                # pylint: disable-next=protected-access
                self.hass.services._services.setdefault(  # noqa: SLF001
                    service.domain,
                    {},
                )[service.service] = service.overriden_service

                # Flush service description schema cache
                self.hass.data.pop(SERVICE_DESCRIPTION_CACHE, None)

        self.async_clear_service_translation_overrides()
        async_remove_service_icons(self.hass, self._injected_service_icons)
