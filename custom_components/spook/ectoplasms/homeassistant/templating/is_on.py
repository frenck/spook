"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.template import is_state

from ....templating import AbstractSpookTemplateFunction

if TYPE_CHECKING:
    from collections.abc import Callable


class SpookTemplateFunction(AbstractSpookTemplateFunction):
    """Spook template function to test if an entity is "on"."""

    name = "is_on"
    test_name = "on"

    is_filter = True
    is_global = True
    is_test = True

    def _function(
        self,
        entity_id: str | list[str],
    ) -> bool:
        """Check if the current state of an entity is "on"."""
        if isinstance(entity_id, list):
            return all(is_state(self.hass, entity, "on") for entity in entity_id)
        return is_state(self.hass, entity_id, "on")

    def function(self) -> Callable[..., Any]:
        """Return the python method that runs this template function."""
        return self._function
