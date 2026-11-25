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

What is read for an automation or a script is kept with that automation or
script, see `reading_for`. A reload that changes one makes Home Assistant
drop it for a new one, and what was read from the old configuration goes
with it. Kept anywhere else, those readings would pile up with every reload.
"""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# How many readings of templates and of configurations are kept. Enough for
# every template, automation, script and template helper of a large house,
# and the copies made of them along the way. A round goes through all of
# them in the same order every time, so a cache that holds fewer than that
# drops each one right before it is asked for again and never hits.
#
# Counted on a house with about 23,000 distinct templates in its automations,
# scripts and dashboards: the readers of one template each keep about that
# many, `_expressions` about twice that, and the lookup of areas, floors and
# labels keeps one per template and per kind, about 69,000. Anything below
# that last number misses on every one of them in the second round.
CACHE_SIZE = 131072

# Off while a configuration is read that was put together for that reading.
_REMEMBERING: ContextVar[bool] = ContextVar("spook_remembering", default=True)


@contextmanager
def read_once() -> Iterator[None]:
    """Read configurations without remembering them.

    For a configuration put together for one reading, like a copy of a
    helper's options: no one hands that very object in again, so remembering
    it would only keep it, and what was read from it, until the cache drops
    it. What is already remembered is still handed out.

    Held per task, so a turn handed to another task in the middle of the
    reading does not change what that task remembers.
    """
    token = _REMEMBERING.set(False)
    try:
        yield
    finally:
        _REMEMBERING.reset(token)


# Whose configuration is being read: the automation or script a repair is
# looking at. Held per task, like `_REMEMBERING`.
_OWNER: ContextVar[Any] = ContextVar("spook_reading_for", default=None)

# What was read, per owner and per reader. Held weakly: when Home Assistant
# drops an automation or script, everything read from it is dropped with it,
# the copies made of its configuration included.
_READINGS: WeakKeyDictionary[Any, dict[Any, dict[Any, Any]]] = WeakKeyDictionary()


@contextmanager
def reading_for(owner: Any) -> Iterator[None]:
    """Keep what is read in here with ``owner``, for as long as it lives."""
    token = _OWNER.set(owner)
    try:
        yield
    finally:
        _OWNER.reset(token)


def owned_readings(reader: Any) -> dict[Any, Any] | None:
    """Return what ``reader`` read for the current owner, to look up and add to.

    None when there is no owner to keep readings with.
    """
    if (owner := _OWNER.get()) is None:
        return None

    try:
        return _READINGS.setdefault(owner, {}).setdefault(reader, {})
    except TypeError:
        # An owner that cannot be held weakly would be kept alive by its own
        # readings, so it is treated as no owner at all.
        return None


def per_configuration[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Remember what ``func`` reads from a configuration, per configuration.

    Keyed by the configuration itself, not by what it holds: comparing two
    configurations costs as much as reading one. The configuration is kept
    with what was read from it, so no other one can take its place under the
    same key while it is remembered. Only a configuration read as a whole,
    a mapping or a list, and only when nothing else is handed in.

    Inside `reading_for` it is kept with the automation or script being read,
    and goes when that one goes. Anywhere else it is kept here, up to
    `CACHE_SIZE` readings.

    What is handed out is shared, so whoever gets it reads it and never
    changes it.
    """
    remembered: OrderedDict[int, tuple[Any, R]] = OrderedDict()

    @wraps(func)
    def _read(*args: P.args, **kwargs: P.kwargs) -> R:
        if kwargs or len(args) != 1 or not isinstance(args[0], (dict, list)):
            return func(*args, **kwargs)

        config = args[0]
        if (readings := owned_readings(func)) is not None:
            known = readings.get(id(config))
            if known is not None and known[0] is config:
                return known[1]

            result = func(*args, **kwargs)
            if _REMEMBERING.get():
                readings[id(config)] = (config, result)
            return result

        if (known := remembered.get(id(config))) is not None and known[0] is config:
            remembered.move_to_end(id(config))
            return known[1]

        result = func(*args, **kwargs)
        if not _REMEMBERING.get():
            return result
        remembered[id(config)] = (config, result)
        if len(remembered) > CACHE_SIZE:
            remembered.popitem(last=False)
        return result

    _read.cache_clear = remembered.clear  # type: ignore[attr-defined]
    return _read


# What has been read from dashboards, to be forgotten whenever one changes.
_DASHBOARD_READERS: list[Callable[[], None]] = []


def per_dashboard_node[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Remember what ``func`` reads from a part of a dashboard, per part.

    The same as `per_configuration`, with one difference: all of it is
    forgotten when Home Assistant says a dashboard changed. Home Assistant
    hands out a new configuration when a dashboard is saved, so the old
    readings would not be asked for again anyway. But a dashboard is shared
    with whatever else runs in the house, and one that changes in place under
    the same object would otherwise keep its old readings.
    """
    remembering = per_configuration(func)
    _DASHBOARD_READERS.append(remembering.cache_clear)  # type: ignore[attr-defined]
    return remembering


def forget_dashboards() -> None:
    """Forget everything read from dashboards."""
    for forget in _DASHBOARD_READERS:
        forget()
