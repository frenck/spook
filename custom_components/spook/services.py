"""Spook - Your homie."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast, final

from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    __short_version__ as current_version,
)
from homeassistant.core import (
    Event,
    HomeAssistant,
    Service,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM
from homeassistant.helpers.service import (
    SERVICE_DESCRIPTION_CACHE,
    _load_services_file,
    async_register_admin_service,
    async_set_service_schema,
)
from homeassistant.helpers.translation import (
    _async_get_translations_cache,
    async_get_cached_translations,
    async_get_translations,
)
from homeassistant.loader import async_get_integration

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType


_EntityT = TypeVar("_EntityT", bound=Entity, default=Entity)
GHOST = "👻"
SERVICE_TRANSLATION_CATEGORY = "services"


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
    def async_register(self) -> None:
        """Handle the service call."""
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
    def async_register(self) -> None:
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

    @abstractmethod
    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        raise NotImplementedError


class AbstractSpookAdminService(AbstractSpookServiceBase):
    """Abstract class to hold a Spook admin service."""

    @final
    @callback
    def async_register(self) -> None:
        """Register the service with Home Assistant."""
        if self.domain != DOMAIN and self.domain not in self.hass.config.components:
            LOGGER.debug(
                "Not registering Spook %s.%s admin service, %s is not loaded",
                self.domain,
                self.service,
                self.domain,
            )
            return

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
        )

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
    def async_register(self) -> None:
        """Register the service with Home Assistant."""
        LOGGER.debug(
            "Registering Spook entity service: %s.%s for platform %s",
            self.domain,
            self.service,
            self.platform,
        )

        if not (
            platform := next(
                platform
                for platform in self.hass.data[DATA_ENTITY_PLATFORM][self.domain]
                if platform.domain == self.platform
            )
        ):
            msg = (
                f"Could not find platform {self.platform} for domain "
                f"{self.domain} to register service: "
                f"{self.domain}.{self.service}",
            )
            raise RuntimeError(msg)

        platform.async_register_entity_service(
            name=self.service,
            func=self.async_handle_service,
            schema=self.schema,
            required_features=self.required_features,
            supports_response=self.supports_response,
        )

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

    @final
    @callback
    def async_register(self) -> None:
        """Register the service with Home Assistant."""
        LOGGER.debug(
            "Registering Spook entity component service: %s.%s",
            self.domain,
            self.service,
        )

        if self.domain not in self.hass.data[DATA_INSTANCES]:
            msg = (
                f"Could not find entity component {self.domain} to register "
                f"service: {self.domain}.{self.service}",
            )
            raise RuntimeError(msg)

        component: EntityComponent[Entity] = self.hass.data[DATA_INSTANCES][self.domain]

        component.async_register_entity_service(
            name=self.service,
            func=self.async_handle_service,
            schema=self.schema,
            required_features=self.required_features,
            supports_response=self.supports_response,
        )

    @abstractmethod
    async def async_handle_service(
        self,
        entity: _EntityT,
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle the service call."""
        raise NotImplementedError


@dataclass
class SpookServiceManager:
    """Class to manage Spook services."""

    hass: HomeAssistant

    _services: set[AbstractSpookService] = field(default_factory=set)
    _service_schemas: dict[str, Any] = field(default_factory=dict)
    _service_translation_overrides: dict[tuple[str, str, str], str | None] = field(
        default_factory=dict
    )
    _translation_listener: Callable[[], None] | None = None

    def __post_init__(self) -> None:
        """Post initialization."""
        LOGGER.debug("Spook service manager initialized")

    async def async_setup(self) -> None:
        """Set up the Spook services."""
        LOGGER.debug("Setting up Spook services")

        # Load service schemas
        integration = await async_get_integration(self.hass, DOMAIN)
        # Ensure compatibility with Home Assistant version
        # As of Home Assistant 2025.10, the _load_services_file function no
        # longer has the hass parameter.
        if AwesomeVersion(current_version) >= AwesomeVersion("2025.10"):
            self._service_schemas = cast(
                dict[str, Any],
                await self.hass.async_add_executor_job(
                    _load_services_file,
                    integration,
                ),
            )
        else:
            self._service_schemas = cast(
                dict[str, Any],
                await self.hass.async_add_executor_job(
                    _load_services_file,
                    self.hass,
                    integration,
                ),
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

        for module in modules:
            service = module.SpookService(self.hass)
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

            self.async_register_service(service)

        await self.async_inject_service_translations()
        self._translation_listener = self.hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE,
            self._async_core_config_updated,
        )

    @callback
    def async_register_service(self, service: AbstractSpookService) -> None:
        """Register a Spook service."""
        service.async_register()
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
                .setdefault(
                    SERVICE_TRANSLATION_CATEGORY,
                    {},
                )
                .setdefault(domain, {})
            )

        return cache.get(language, {}).get(SERVICE_TRANSLATION_CATEGORY, {}).get(domain)

    @callback
    def _inject_service_translation_strings(
        self,
        service: AbstractSpookService,
        cached_spook_translations: dict[str, str],
    ) -> None:
        """Inject service translation strings into Home Assistant's cache."""
        language = self.hass.config.language
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

    async def async_inject_service_translations(self) -> None:
        """Inject Spook service strings into Home Assistant translations."""
        services = [
            service
            for service in self._services
            if self._service_schema_key(service) in self._service_schemas
        ]

        if not services:
            return

        await async_get_translations(
            self.hass,
            self.hass.config.language,
            SERVICE_TRANSLATION_CATEGORY,
            {DOMAIN, *(service.domain for service in services)},
        )
        cached_spook_translations = async_get_cached_translations(
            self.hass,
            self.hass.config.language,
            SERVICE_TRANSLATION_CATEGORY,
            DOMAIN,
        )

        for service in services:
            self._inject_service_translation_strings(
                service,
                cached_spook_translations,
            )

    async def _async_core_config_updated(self, event: Event) -> None:
        """Re-inject service translations when the language changes."""
        if "language" not in event.data:
            return
        await self.async_inject_service_translations()

    @callback
    def async_clear_service_translation_overrides(self) -> None:
        """Restore translation strings that were overridden by Spook."""
        for (
            language,
            domain,
            key,
        ), original_value in self._service_translation_overrides.items():
            component_cache = self._translation_component_cache(language, domain)
            if component_cache is None:
                continue

            if original_value is None:
                component_cache.pop(key, None)
            else:
                component_cache[key] = original_value

        self._service_translation_overrides.clear()

    @callback
    def async_on_unload(self) -> None:
        """Tear down the Spook services."""
        LOGGER.debug("Tearing down Spook services")
        if self._translation_listener:
            self._translation_listener()
            self._translation_listener = None

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
