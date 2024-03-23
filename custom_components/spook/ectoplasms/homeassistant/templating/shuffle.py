"""Spook - Your homie."""

from __future__ import annotations

from random import Random, shuffle
from typing import TYPE_CHECKING, Any

from ....templating import AbstractSpookTemplateFunction

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class SpookTemplateFunction(AbstractSpookTemplateFunction):
    """Spook template function to shuffle lists."""

    name = "shuffle"

    requires_hass_object = False
    is_available_in_limited_environment = True
    is_filter = True
    is_global = True

    def shuffle(self, items: Iterable[Any], seed: Any = None) -> Iterable[Any]:
        """Shuffle a list, either with a seed or without."""
        items = list(items)
        if seed:
            r = Random(seed)  # noqa: S311
            r.shuffle(items)
        else:
            shuffle(items)
        return items

    def function(self) -> Callable[..., Any]:
        """Return the python method that runs this template function."""
        return self.shuffle
