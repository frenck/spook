"""Spook - Your homie. Reading a configuration once, however many ask.

Every repair about automations and scripts walks every one of them, and each
of those walks starts the same way: the configuration without its disabled
steps, the names it gives its templates, the templates it holds, the targets
it names. A dozen repairs reading a house of a few hundred automations after
a reload work all of that out a few thousand times, for the same handful of
configurations, on the event loop. On a small machine that holds Home
Assistant up for a minute. #2005.

What is read here only depends on the configuration handed in, so it is
worked out once per configuration and handed out again after that. Home
Assistant builds a new configuration on every reload and never changes one
it has handed out, so a configuration that is still the same object still
reads the same.
"""

from __future__ import annotations

from collections import OrderedDict
from functools import wraps
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

# How many readings of templates and of configurations are kept. Enough for
# every template, automation, script and template helper of a large house,
# and the copies made of them along the way. A round goes through all of
# them in the same order every time, so a cache that holds fewer than that
# drops each one right before it is asked for again and never hits.
CACHE_SIZE = 8192


def per_configuration[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Remember what ``func`` reads from a configuration, per configuration.

    Keyed by the configuration itself, not by what it holds: comparing two
    configurations costs as much as reading one. The configuration is kept
    with what was read from it, so no other one can take its place under the
    same key while it is remembered. Only a configuration read as a whole,
    a mapping or a list, and only when nothing else is handed in.

    What is handed out is shared, so whoever gets it reads it and never
    changes it.
    """
    remembered: OrderedDict[int, tuple[Any, R]] = OrderedDict()

    @wraps(func)
    def _read(*args: P.args, **kwargs: P.kwargs) -> R:
        if kwargs or len(args) != 1 or not isinstance(args[0], (dict, list)):
            return func(*args, **kwargs)

        config = args[0]
        if (known := remembered.get(id(config))) is not None and known[0] is config:
            remembered.move_to_end(id(config))
            return known[1]

        result = func(*args, **kwargs)
        remembered[id(config)] = (config, result)
        if len(remembered) > CACHE_SIZE:
            remembered.popitem(last=False)
        return result

    _read.cache_clear = remembered.clear  # type: ignore[attr-defined]
    return _read
