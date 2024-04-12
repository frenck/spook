"""Spook - Your homie."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from ....templating import AbstractSpookTemplateFunction

if TYPE_CHECKING:
    from collections.abc import Callable


class SpookTemplateFunction(AbstractSpookTemplateFunction):
    """Spook template function to flatten lists of lists."""

    name = "flatten"

    is_filter = True
    is_global = True

    def _function(
        self,
        value: Iterable[Any],
        levels: int | None = None,
    ) -> list[Any]:
        """Flattens a list of lists."""
        flattend: list[Any] = []
        for item in value:
            if isinstance(item, Iterable) and not isinstance(item, str):
                if levels is None:
                    flattend.extend(self._function(item))
                elif levels >= 1:
                    flattend.extend(self._function(item, levels=(levels - 1)))
                else:
                    flattend.append(item)
            else:
                flattend.append(item)
        return flattend

    def function(self) -> Callable[..., Any]:
        """Return the python method that runs this template function."""
        return self._function
