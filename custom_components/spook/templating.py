"""Spook - Your homie."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, final

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import TemplateEnvironment

from .const import LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType


class AbstractSpookTemplateFunction(ABC):
    """Abstract base class to hold a Spook template function."""

    hass: HomeAssistant
    name: str
    filter_name: str | None = None
    test_name: str | None = None

    requires_hass_object: bool = True
    is_available_in_limited_environment: bool = False
    is_filter: bool = False
    is_global: bool = False
    is_test: bool = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the template function."""
        self.hass = hass

    @abstractmethod
    def function(self) -> Callable[..., Any]:
        """Return the python method that runs this template function."""
        raise NotImplementedError

    @final
    @callback
    def async_register(
        self, environment: TemplateEnvironment, *, is_limited: bool | None = False
    ) -> None:
        """Register the template method."""
        if environment.hass is None and self.requires_hass_object:
            return

        if self.is_global:
            # pylint: disable-next=protected-access
            if is_limited and not self.is_available_in_limited_environment:
                environment.globals[self.name] = unsupported_in_limited_environment(
                    self.name
                )
            else:
                environment.globals[self.name] = self.function()

        if self.is_filter:
            # pylint: disable-next=protected-access
            if is_limited and not self.is_available_in_limited_environment:
                environment.filters[self.filter_name or self.name] = (
                    unsupported_in_limited_environment(self.name)
                )
            else:
                environment.filters[self.filter_name or self.name] = self.function()

        if self.is_test:
            if is_limited and not self.is_available_in_limited_environment:
                environment.tests[self.test_name or self.name] = (
                    unsupported_in_limited_environment(self.name)
                )
            else:
                environment.tests[self.test_name or self.name] = self.function()

    @final
    @callback
    def async_unregister(self, environment: TemplateEnvironment) -> None:
        """Unregister the template method."""
        environment.globals.pop(self.name, None)
        environment.filters.pop(self.name, None)
        environment.tests.pop(self.name, None)


def unsupported_in_limited_environment(name: str) -> Callable[[], NoReturn]:
    """Return a function that raises TemplateError when called."""

    def warn_unsupported(*_: Any, **__: Any) -> NoReturn:
        msg = f"Use of '{name}' is not supported in limited templates"
        raise TemplateError(msg)

    return warn_unsupported


@dataclass
class SpookTemplateFunctionManager:
    """Class to manage Spook template functions."""

    hass: HomeAssistant

    _template_functions: set[AbstractSpookTemplateFunction] = field(default_factory=set)
    _service_schemas: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Post initialization."""
        LOGGER.debug("Spook template function manager initialized")

    async def async_setup(self) -> None:
        """Set up the Spook services."""
        LOGGER.debug("Setting up Spook template functions")

        modules: list[ModuleType] = []

        def _load_all_templating_modules() -> None:
            """Load all templating modules."""
            for module_file in Path(__file__).parent.rglob(
                "ectoplasms/*/templating/*.py"
            ):
                if module_file.name == "__init__.py":
                    continue
                module_path = str(module_file.relative_to(Path(__file__).parent))[
                    :-3
                ].replace("/", ".")
                modules.append(importlib.import_module(f".{module_path}", __package__))

        await self.hass.async_add_import_executor_job(_load_all_templating_modules)

        for module in modules:
            template_function = module.SpookTemplateFunction(self.hass)

            LOGGER.debug(
                "Registering Spook template function: %s",
                template_function.name,
            )

            template_function.async_register(self.hass.data["template.environment"])
            template_function.async_register(
                self.hass.data["template.environment_strict"]
            )
            template_function.async_register(
                self.hass.data["template.environment_limited"], is_limited=True
            )
            self._template_functions.add(template_function)

        # Patch TemplateEnvironment for new instances
        template_functions = self._template_functions

        def template_environment_init(
            self: TemplateEnvironment,
            hass: HomeAssistant | None,
            limited: bool | None = False,  # noqa: FBT002
            strict: bool | None = False,  # noqa: FBT002
            log_fn: Callable[[int, str], None] | None = None,
        ) -> None:
            self.original_init_before_spook(hass, limited, strict, log_fn)
            # Register the Spook template functions
            for template_function in template_functions:
                template_function.async_register(self, is_limited=limited)

        # Keep a reference to the original __init__ method, so we can restore on unload
        TemplateEnvironment.original_init_before_spook = TemplateEnvironment.__init__
        TemplateEnvironment.__init__ = template_environment_init

    @callback
    def async_on_unload(self) -> None:
        """Tear down the Spook template functions."""
        LOGGER.debug("Tearing down Spook template functions")
        for function in self._template_functions:
            LOGGER.debug(
                "Unregistering Spook template function: %s",
                function.name,
            )
            function.async_unregister(self.hass.data["template.environment"])
            function.async_unregister(self.hass.data["template.environment_strict"])
            function.async_unregister(self.hass.data["template.environment_limited"])
            self._template_functions.discard(function)

        # Restore the original TemplateEnvironment.__init__ method
        TemplateEnvironment.__init__ = TemplateEnvironment.original_init_before_spook
        del TemplateEnvironment.original_init_before_spook
