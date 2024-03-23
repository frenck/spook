"""Spook - Your homie."""

from __future__ import annotations

from collections.abc import Iterable
import fnmatch
from typing import TYPE_CHECKING, Any

from ....templating import AbstractSpookTemplateFunction

if TYPE_CHECKING:
    from collections.abc import Callable


class SpookTemplateFunction(AbstractSpookTemplateFunction):
    """Spook template function to filter using fnmatch."""

    name = "fnmatch_filter"

    requires_hass_object = False
    is_available_in_limited_environment = True
    is_filter = True
    is_global = True

    def _function(
        self,
        value: Iterable[str],
        pattern: str,
        case_sensitive: bool = False,  # noqa: FBT001, FBT002
    ) -> bool | list[str]:
        """Unix file pattern matching a string or list."""
        if isinstance(value, Iterable) and not isinstance(value, str):
            if case_sensitive:
                return [x for x in value if fnmatch.fnmatchcase(x, pattern)]
            return fnmatch.filter(value, pattern)

        msg = f"fnmatch() argument must be a list, not {type(value)}"
        raise TypeError(msg)

    def function(self) -> Callable[..., Any]:
        """Return the python method that runs this template function."""
        return self._function
