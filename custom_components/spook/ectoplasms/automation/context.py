"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import Context


def run_context(variables: Any) -> Context | None:
    """Return the context the current automation or script run started with.

    Home Assistant puts the run's context in the variables of every top-level
    script run, which is what an automation is. Reading it there works for
    every trigger type, unlike digging through ``trigger.to_state.context``,
    which only exists for the trigger types that carry a state.

    Returns ``None`` when there is no context to read, which happens when a
    condition is evaluated outside a run (a template preview, for example).
    """
    if variables is None:
        return None

    try:
        context = variables["context"]
    except TypeError, KeyError, IndexError:
        return None

    # Duck-typed rather than isinstance: this is read-only, and a mapping
    # standing in for a Context during a template render is just as usable.
    return context if hasattr(context, "user_id") else None
