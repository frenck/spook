"""Spook - Your homie."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from ....templating import AbstractSpookTemplateFunction

if TYPE_CHECKING:
    from collections.abc import Callable


class SpookTemplateFunction(AbstractSpookTemplateFunction):
    """Spook template function to generate sha256 hashes."""

    name = "sha256"

    requires_hass_object = False
    is_available_in_limited_environment = True
    is_filter = True
    is_global = True

    def _function(
        self,
        value: str,
    ) -> str:
        """Generate sha256 hash from a string."""
        return hashlib.sha256(value.encode()).hexdigest()

    def function(self) -> Callable[..., Any]:
        """Return the python method that runs this template function."""
        return self._function
