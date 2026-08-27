"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import Context

# Where a trigger keeps the context of the thing that set it off. A state
# trigger carries the state it changed to; an event trigger carries the event.
#
# `from_state` is deliberately not here. It is the state before the change, so
# its context belongs to whoever wrote the value that is now being replaced. A
# user flipping a switch and an integration turning it back a minute later
# would both look like the user.
_TRIGGER_CONTEXT_KEYS = ("to_state", "event")


def _candidates(variables: Any) -> Iterator[Any]:
    """Yield every place the run's originating context might be found."""
    # A script run inherits the caller's context, and the script engine puts
    # it straight into the variables. This is the direct answer when it is
    # there: a user pressing "Run" on a script, or calling it from the API.
    yield variables.get("context")

    # An automation does not inherit it. It deliberately starts a fresh
    # context carrying only a parent_id (`components/automation/__init__.py`,
    # `Context(parent_id=parent_id)`), so the user has to come from whatever
    # the trigger captured. Nothing resolves that parent back to a context,
    # which is why forcing a run with `automation.trigger` cannot be
    # attributed to anybody.
    trigger = variables.get("trigger")
    if not hasattr(trigger, "get"):
        return

    for key in _TRIGGER_CONTEXT_KEYS:
        yield getattr(trigger.get(key), "context", None)


def run_context(variables: Any) -> Context | None:
    """Return the context of whoever set this run going, if it can be known.

    Returns ``None`` when nothing in reach names a user: a time trigger, a
    template trigger, a run forced through `automation.trigger`, or a
    condition being evaluated outside a run at all. Callers should read that
    as "not a person", which is the truth as far as anything here can tell.

    A context that exists but names nobody is the same answer as no context,
    so it is not worth telling them apart.
    """
    if not hasattr(variables, "get"):
        return None

    for context in _candidates(variables):
        if getattr(context, "user_id", None) is not None:
            return context

    return None
