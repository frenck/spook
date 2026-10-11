"""Spook - Your homie. Templates that can never pass, read from their text alone.

A template condition passes only when it renders `true`, and a template
trigger only fires on something that reads as true. A template that was
written so that it can never render that loads fine, never passes, and Home
Assistant says nothing. Quotes inside a `>-` block, a missing `{{`, YAML pasted
into the template field, a YAML comment inside Jinja, a condition that renders
`on`: all of them end up as text that is always there in the output.

Everything here reads the template's own text and Jinja's parse of it, never
a state, a variable or anything else only a run knows. When the output
depends on any of that, the template is not judged. A wrong answer reports a
working automation as broken; a missed one only stays hidden a while longer.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from itertools import product
from typing import TYPE_CHECKING, Any
import unicodedata

from jinja2 import Environment, TemplateSyntaxError, nodes

from homeassistant.helpers.template import (
    Template,
    is_template_string,
    result_as_boolean,
)

from .reference_extraction import without_disabled_steps, without_never_rendered

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class TemplateRole(StrEnum):
    """What Home Assistant does with a template, which decides what passes."""

    # `helpers/condition.py` `async_template`: the render, lowercased, has to
    # be exactly `true`. Nothing else passes, not `on`, not `1`.
    CONDITION = "condition"

    # `components/template/trigger.py`: the render goes through
    # `result_as_boolean`, which also takes `on`, `yes`, `1` and the like.
    TRIGGER = "trigger"

    # `helpers/script.py` `_async_step_wait_template`: first checked like a
    # condition, then watched by `async_track_template`, which takes what a
    # trigger takes, but only when its render changes from false to true. A
    # template that cannot render both never makes that change, so for that
    # one only the condition check counts.
    WAIT = "wait"


# Only ever used to parse, with the tags Home Assistant adds to Jinja's own.
# Like the parsers in the other readers: its other extensions only add
# functions, filters and tests, which a parse never looks up.
_JINJA_PARSER = Environment(
    autoescape=True, extensions=["jinja2.ext.do", "jinja2.ext.loopcontrols"]
)

# Every text a piece of the output can be, or `None` when that is only known
# while running. A piece that could be anything at all is `None` too.
type _Piece = frozenset[str] | None

# Branches multiply. Past this many outputs the template is read piece by
# piece instead of as a whole.
_MOST_OUTPUTS = 256

# Constants Jinja prints the way Python's `str` does.
_PRINTED_AS_STR = (str, bool, int, float)

# Statements that print nothing themselves: `{% set %}`, `{% do %}`, a macro
# being defined, and imports.
_SILENT_STATEMENTS = (
    nodes.Assign,
    nodes.AssignBlock,
    nodes.ExprStmt,
    nodes.FromImport,
    nodes.Import,
    nodes.Macro,
)

# What a render that reads as true can start with, once Home Assistant has
# stripped it, lowercased. `true`, `yes`, `on` and `enable` as text, `True`
# as Python, and a number other than zero: a digit, a sign or a dot. Python
# also skips a comment, a line continuation and brackets around `True`, as
# `literal_eval` does. Digits are any Unicode digit, like core's regex.
_TRUTHY_STARTS = frozenset("tyoe+-.(#\\")

# The only characters, lowercased, a condition's output can hold besides
# whitespace.
_LETTERS_OF_TRUE = frozenset("true")


def _combined(pieces: list[_Piece]) -> frozenset[str] | None:
    """Return every text the pieces can make together, or `None`."""
    outputs: frozenset[str] = frozenset({""})
    for piece in pieces:
        if piece is None:
            return None
        outputs = frozenset(before + after for before, after in product(outputs, piece))
        if len(outputs) > _MOST_OUTPUTS:
            return None
    return outputs


def _expression(node: nodes.Node) -> _Piece:
    """Return what an expression can print, when that is in the text."""
    if isinstance(node, nodes.TemplateData):
        return frozenset({node.data})

    if isinstance(node, nodes.Const) and (
        node.value is None or isinstance(node.value, _PRINTED_AS_STR)
    ):
        return frozenset({str(node.value)})

    if isinstance(node, nodes.CondExpr):
        # Without an `else`, the other way prints an undefined value, and Home
        # Assistant prints that as nothing.
        otherwise = frozenset({""}) if node.expr2 is None else _expression(node.expr2)
        if (chosen := _expression(node.expr1)) is None or otherwise is None:
            return None
        return chosen | otherwise

    return None


def _branches(node: nodes.If) -> _Piece:
    """Return what an `if` can print, whichever branch it takes.

    Every branch counts, whatever its test says: which one runs is only
    known while running. Without an `else`, printing nothing is one of them.
    """
    bodies = [node.body, *(branch.body for branch in node.elif_), node.else_]

    outputs: set[str] = set()
    for body in bodies:
        if (pieces := _pieces(body)) is None or (printed := _combined(pieces)) is None:
            return None
        outputs |= printed
    return frozenset(outputs)


def _pieces(body: list[nodes.Node]) -> list[_Piece] | None:
    """Return the output of a body, in order, one piece per printed part.

    `None` when the template takes another one's place with `{% extends %}`,
    as then this text is not what prints.
    """
    pieces: list[_Piece] = []
    for node in body:
        if isinstance(node, nodes.Extends):
            return None
        if isinstance(node, nodes.Output):
            pieces.extend(_expression(child) for child in node.nodes)
        elif isinstance(node, nodes.If):
            pieces.append(_branches(node))
        elif not isinstance(node, _SILENT_STATEMENTS):
            # A loop, an include, a call block and the like: what they print
            # depends on what they run over.
            pieces.append(None)
    return pieces


@lru_cache(maxsize=1024)
def _output_pieces(template_str: str) -> tuple[_Piece, ...] | None:
    """Return the pieces a template's output is made of, in order.

    `None` for a template Jinja cannot read. Home Assistant refuses to load
    that, and says so itself. Pure in its argument, so cached.
    """
    try:
        parsed = _JINJA_PARSER.parse(template_str)
    except TemplateSyntaxError:
        return None

    if (pieces := _pieces(parsed.body)) is None:
        return None
    return tuple(pieces)


def _passes(hass: HomeAssistant, role: TemplateRole, output: str) -> bool | None:
    """Return whether Home Assistant takes this output as passing.

    Asked of Home Assistant itself, by rendering the output as a template
    without any Jinja: that goes through the same stripping and parsing as a
    real render. `None` for an output that holds Jinja of its own, which
    would be rendered again rather than taken as it is.
    """
    if is_template_string(output):
        return None

    rendered = Template(output, hass)
    if role is TemplateRole.CONDITION:
        return rendered.async_render(parse_result=False).lower() == "true"
    return result_as_boolean(rendered.async_render())


def _spoils_true(text: str) -> bool:
    """Return whether output holding this text can never be `true`.

    The whole output, stripped and lowercased, has to be exactly `true`, so
    any other character that is not whitespace rules it out, wherever it is.
    """
    return any(
        not character.isspace() and character.lower() not in _LETTERS_OF_TRUE
        for character in text
    )


def _could_start_truthy(character: str) -> bool:
    """Return whether a render reading as true can start with this character.

    Python reads some characters as others, a fullwidth T as a plain one, so those are
    looked at as Python sees them as well.
    """
    return any(
        candidate.lower() in _TRUTHY_STARTS or candidate.isdecimal()
        for candidate in (character, unicodedata.normalize("NFKC", character)[:1])
    )


def _starts_untruthy(pieces: tuple[_Piece, ...]) -> bool:
    """Return whether the output always starts with what never reads as true.

    The first piece that prints anything decides the first character. Only
    when every text it can be prints something: one that can be empty hands
    that over to whatever comes after it.
    """
    for piece in pieces:
        if piece is None:
            return False

        stripped = {text.lstrip() for text in piece}
        if stripped == {""}:
            continue
        if "" in stripped:
            return False
        return not any(_could_start_truthy(text[0]) for text in stripped)
    return False


def _wait_never_ends(hass: HomeAssistant, outputs: frozenset[str]) -> bool:
    """Return whether a wait with these outputs can never end, but on timeout.

    The check up front takes only `true`. The watch after it only fires when
    the render goes from something that is not true to something that is, so
    it needs at least one of each. Every output `on` or `yes` never does.
    """
    if any(
        _passes(hass, TemplateRole.CONDITION, output) is not False for output in outputs
    ):
        return False

    reads_as_true = {_passes(hass, TemplateRole.TRIGGER, output) for output in outputs}
    if None in reads_as_true:
        return False
    return reads_as_true != {True, False}


def never_passes(hass: HomeAssistant, role: TemplateRole, template_str: str) -> bool:
    """Return whether a template can never render what its role needs.

    Read as a whole when every text it can print is in the template itself,
    whichever branch it takes. Otherwise piece by piece: a condition with a
    piece that always holds something besides `true`, or a trigger or wait
    whose output always starts with what nothing true starts with.
    """
    # Home Assistant's own test for whether there is any Jinja in it. Without
    # it, the text is what renders, and for a wait it is never watched.
    if not is_template_string(template_str):
        static_role = TemplateRole.CONDITION if role is TemplateRole.WAIT else role
        return _passes(hass, static_role, template_str) is False

    if (pieces := _output_pieces(template_str)) is None:
        return False

    if (outputs := _combined(list(pieces))) is not None:
        if role is TemplateRole.WAIT:
            return _wait_never_ends(hass, outputs)
        return all(_passes(hass, role, output) is False for output in outputs)

    if role is TemplateRole.CONDITION:
        return any(
            piece is not None and piece and all(_spoils_true(text) for text in piece)
            for piece in pieces
        )
    return _starts_untruthy(pieces)


def _as_list(value: Any) -> list[Any]:
    """Return a value Home Assistant takes as one or a list, as a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _template_text(value: Any) -> str | None:
    """Return a configured template as Home Assistant reads it.

    `cv.template` takes any value but a list or a mapping, as its text:
    `value_template: true` in YAML is the template `True`.
    """
    if value is None or isinstance(value, (dict, list)):
        return None
    return str(value)


class _Collector:
    """Walks an automation or a script for the templates that have to pass."""

    def __init__(self) -> None:
        """Start with nothing found."""
        self.found: list[tuple[TemplateRole, str]] = []

    def _add(self, role: TemplateRole, value: Any) -> None:
        if (text := _template_text(value)) is not None:
            self.found.append((role, text))

    def triggers(self, triggers: Any) -> None:
        """Collect template triggers, also from a group of triggers."""
        for trigger in _as_list(triggers):
            if not isinstance(trigger, dict):
                continue
            if "triggers" in trigger and len(trigger) == 1:
                self.triggers(trigger["triggers"])
                continue
            if trigger.get("trigger", trigger.get("platform")) == "template":
                self._add(TemplateRole.TRIGGER, trigger.get("value_template"))

    def conditions(self, conditions: Any) -> None:
        """Collect template conditions, written out or as shorthand."""
        for condition in _as_list(conditions):
            if isinstance(condition, str):
                # Home Assistant takes a template on its own as a template
                # condition. Anything else here does not load at all.
                if is_template_string(condition):
                    self._add(TemplateRole.CONDITION, condition)
            elif isinstance(condition, dict):
                self.condition(condition)

    def condition(self, config: dict[str, Any], *, as_step: bool = False) -> None:
        """Collect from one condition, and the ones nested in it."""
        kind = config.get("condition")
        if kind == "template":
            self._add(TemplateRole.CONDITION, config.get("value_template"))
        elif isinstance(kind, list):
            self.conditions(kind)
        elif as_step and isinstance(kind, str) and is_template_string(kind):
            # The shorthand for a condition step: `condition: "{{ ... }}"`.
            self._add(TemplateRole.CONDITION, kind)

        for key in ("conditions", "and", "or", "not"):
            if key in config:
                self.conditions(config[key])

    def actions(self, actions: Any) -> None:
        """Collect from every step, however deeply nested."""
        for step in _as_list(actions):
            if isinstance(step, dict):
                self.step(step)

    def step(self, step: dict[str, Any]) -> None:
        """Collect from one step and the steps it holds."""
        if "wait_template" in step:
            self._add(TemplateRole.WAIT, step["wait_template"])
        if "wait_for_trigger" in step:
            self.triggers(step["wait_for_trigger"])
        if "condition" in step:
            self.condition(step, as_step=True)

        if "if" in step:
            self.conditions(step["if"])
            self.actions(step.get("then"))
            self.actions(step.get("else"))

        if "choose" in step:
            for option in _as_list(step["choose"]):
                if isinstance(option, dict):
                    self.conditions(option.get("conditions"))
                    self.actions(option.get("sequence"))
            self.actions(step.get("default"))

        if isinstance(repeat := step.get("repeat"), dict):
            self.conditions(repeat.get("while"))
            self.conditions(repeat.get("until"))
            self.actions(repeat.get("sequence"))

        # A branch of `parallel` is a step, or a `sequence` of them, which is
        # a step of its own too.
        self.actions(step.get("parallel"))
        self.actions(step.get("sequence"))


def _one_line(template_str: str) -> str:
    """Return a template on one line, the way the issue shows it."""
    return " ".join(template_str.split())


def never_true_templates(hass: HomeAssistant, domain: str, config: Any) -> set[str]:
    """Return the templates in an automation or script that can never pass.

    The triggers, conditions and actions of an automation, or the `sequence`
    of a script, read as written. Disabled ones are left out: they never
    render. Each template is returned on one line.
    """
    if not isinstance(config, dict):
        return set()

    running = without_never_rendered(without_disabled_steps(config))

    # Both the current keys and the old ones; Home Assistant takes either.
    collector = _Collector()
    if domain == "script":
        collector.actions(running.get("sequence"))
    else:
        collector.triggers(running.get("triggers", running.get("trigger")))
        collector.conditions(running.get("conditions", running.get("condition")))
        collector.actions(running.get("actions", running.get("action")))

    return {
        _one_line(template_str)
        for role, template_str in collector.found
        if never_passes(hass, role, template_str)
    }
