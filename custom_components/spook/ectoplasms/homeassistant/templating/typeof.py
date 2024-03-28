"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ....templating import AbstractSpookTemplateFunction

if TYPE_CHECKING:
    from collections.abc import Callable


class SpookTemplateFunction(AbstractSpookTemplateFunction):
    """Spook template function to debug types."""

    name = "typeof"

    requires_hass_object = False
    is_available_in_limited_environment = True
    is_filter = True
    is_global = True

    def function(self) -> Callable[..., Any]:
        """Return the python method that runs this template function."""
        return lambda o: o.__class__.__name__
