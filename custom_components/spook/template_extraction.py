"""Spook - Your homie. Template entity reference extraction helpers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import lru_cache
import re
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, TemplateSyntaxError

from homeassistant.const import Platform
from homeassistant.core import valid_entity_id
from homeassistant.helpers.template import Template

from .const import LOGGER
from .entity_filtering import (
    IGNORED_ENTITY_DOMAINS,
    NEVER_AN_ENTITY_PREFIXES,
    async_drop_existing_action_names,
    async_get_all_entity_ids,
    async_get_all_services,
    is_device_id_shaped,
    split_comma_separated_entity_ids,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant

# Additional known domains that are not in the Platform enum
ADDITIONAL_DOMAINS = [
    "alert",
    "automation",
    "counter",
    "group",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "person",
    "plant",
    "proximity",
    "schedule",
    "script",
    "sun",
    "tag",
    "timer",
    "zone",
]

# Build a list of all known domains
KNOWN_DOMAINS = [platform.value for platform in Platform] + ADDITIONAL_DOMAINS


# Home Assistant core entity ID validation patterns (from homeassistant/core.py)
_OBJECT_ID = r"(?!_)[\da-z_]+(?<!_)"
# Modified _DOMAIN pattern to only match known domains
_DOMAIN = r"(?:" + "|".join(KNOWN_DOMAINS) + r")"
ENTITY_ID_PATTERN = _DOMAIN + r"\." + _OBJECT_ID


# Template function names that accept entity IDs as first parameter
_ENTITY_FUNCTIONS = [
    "states",
    "is_state",
    "state_attr",
    "is_state_attr",
    "has_value",
    "state_translated",
    "device_id",
    "device_name",
    "device_attr",
    "is_device_attr",
    "config_entry_id",
    "area_id",
    "area_name",
    "floor_id",
    "floor_name",
    "is_hidden_entity",
    "expand",
    "distance",
    "closest",
]


# Build regex patterns using Home Assistant's core validation patterns
_STATES_DOMAIN_ENTITY_GROUPS = 2


ENTITY_ID_TEMPLATE_PATTERNS = [
    # Template functions with entity ID as first parameter
    rf"(?:{'|'.join(_ENTITY_FUNCTIONS)})\s*\(\s*['\"]({ENTITY_ID_PATTERN})['\"]",
    # Direct entity state access patterns (states.domain.entity)
    rf"states\.({_DOMAIN})\.({_OBJECT_ID})(?:\.state|\.attributes)",
    # Entity IDs in any quoted context (captures all entity IDs in lists, etc.)
    rf"['\"]({ENTITY_ID_PATTERN})['\"]",
    # Entity IDs followed by filter functions (entity_id | function)
    rf"['\"]({ENTITY_ID_PATTERN})['\"](?:\s*\|\s*(?:{'|'.join(_ENTITY_FUNCTIONS)}))",
]


COMPILED_ENTITY_ID_TEMPLATE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE) for pattern in ENTITY_ID_TEMPLATE_PATTERNS
)


JINJA_COMMENT_PATTERN = re.compile(r"\{#.*?#\}", re.DOTALL)

# The ``device_entities`` template function takes a device registry ID
# directly (no name or entity resolution), so a quoted literal is
# unambiguously a device reference.
_DEVICE_ENTITIES_PATTERN = re.compile(
    r"device_entities\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def is_template_string(value: str) -> bool:
    """Check if a string looks like a Jinja2 template.

    All three of Jinja's delimiters, comments included. A comment on its own
    is a template as far as Home Assistant is concerned, and it will take one
    as a shorthand condition, so anything that does not know that reads it as
    the name of an integration instead. #1520.

    Stricter than `homeassistant.helpers.template.is_template_string`, which
    is happy with an opening delimiter and no closing one. That is deliberate
    and tested: a half-written template is not something to go extracting
    references out of.
    """
    if not isinstance(value, str):
        return False
    return (
        ("{{" in value and "}}" in value)
        or ("{%" in value and "%}" in value)
        or ("{#" in value and "#}" in value)
    )


async def async_extract_entities_from_template_string(
    hass: HomeAssistant,
    template_str: str,
    known_services: set[str] | None = None,
) -> set[str]:
    """Extract entity IDs from a template string using regex analysis.

    This function uses regex patterns based on Home Assistant's core validation
    patterns to find entity IDs referenced in template functions.
    """
    if not is_template_string(template_str):
        return set()

    entities = set()

    # Use regex patterns to find entities
    try:
        regex_entities = extract_entities_from_template_regex(
            hass, template_str, known_services
        )
        entities.update(regex_entities)
    # pylint: disable-next=broad-exception-caught
    except Exception as exc:  # noqa: BLE001 - Keep broad for unexpected regex issues
        LOGGER.debug(
            "Failed to extract entities from template '%s...' using regex.",
            template_str[:50],
            exc_info=exc,  # Pass the exception for logging
        )

    return entities


def _strip_jinja_comments(template_str: str) -> str:
    """Remove Jinja comments from a template string."""
    if "{#" not in template_str:
        return template_str
    return JINJA_COMMENT_PATTERN.sub("", template_str)


# What glues a string to the one next to it in Jinja: `~`, `+` on two
# strings, and nothing at all between two literals, which Jinja joins into
# one. `'sensor.room' + suffix` is the start of an entity ID, not one.
_GLUE = ("~", "+", "'", '"')


def _is_concatenated_template_match(template_str: str, match: re.Match[str]) -> bool:
    """Return if a quoted entity ID literal is part of a concatenated string."""
    groups = match.groups()
    if len(groups) == _STATES_DOMAIN_ENTITY_GROUPS:
        return False

    entity_start, entity_end = match.span(1)
    before_entity = template_str[:entity_start].rstrip()
    after_entity = template_str[entity_end:].lstrip()

    if not (before_entity.endswith(("'", '"')) and after_entity.startswith(("'", '"'))):
        return False

    before_literal = before_entity[:-1].rstrip()
    after_literal = after_entity[1:].lstrip()
    return before_literal.endswith(_GLUE) or after_literal.startswith(_GLUE)


def _is_jinja_import_match(template_str: str, match: re.Match[str]) -> bool:
    """Return if a quoted entity-like literal is a Jinja import filename."""
    groups = match.groups()
    if len(groups) == _STATES_DOMAIN_ENTITY_GROUPS:
        return False

    entity_start, entity_end = match.span(1)
    block_start = template_str.rfind("{%", 0, entity_start)
    expression_start = template_str.rfind("{{", 0, entity_start)
    if block_start == -1 or expression_start > block_start:
        return False

    block_end = template_str.find("%}", entity_end)
    expression_end = template_str.find("}}", entity_end)
    if block_end == -1 or (expression_end != -1 and expression_end < block_end):
        return False

    block = template_str[block_start : block_end + 2]
    return bool(
        re.match(
            r"\{%-?\s*(?:from\s+['\"][^'\"]+['\"]\s+import|import\s+['\"][^'\"]+['\"]\s+as)",
            block,
        )
    )


def _is_string_method_argument_match(template_str: str, match: re.Match[str]) -> bool:
    """Return if an entity-like literal is used as a string method argument."""
    groups = match.groups()
    if len(groups) == _STATES_DOMAIN_ENTITY_GROUPS:
        return False

    entity_start = match.span(1)[0]
    before_entity = template_str[:entity_start].rstrip()
    if not before_entity.endswith(("'", '"')):
        return False

    before_literal = before_entity[:-1].rstrip()
    for method in (".startswith", ".endswith"):
        if method not in before_literal:
            continue

        after_method = before_literal.rsplit(method, maxsplit=1)[1].lstrip()
        if not after_method.startswith("("):
            continue

        between_call_and_argument = after_method[1:].strip()
        if not between_call_and_argument or set(between_call_and_argument) == {"("}:
            return True

    return False


# Filters, tests and methods whose arguments are text to look for or put in,
# never a reference. `replace` is how a template turns one entity ID into its
# sibling: `binary_sensor.` in, `sensor.` out. Neither half is an entity. #1686.
#
# Each only counts when called the way it exists: a bare `replace(...)` is
# not Jinja's filter but somebody's macro, and its arguments can be anything.
_TEXT_ARGUMENT_FILTERS = frozenset(
    {
        "replace",
        "regex_findall",
        "regex_findall_index",
        "regex_match",
        "regex_replace",
        "regex_search",
    }
)
_TEXT_ARGUMENT_TESTS = frozenset({"match", "search"})
_TEXT_ARGUMENT_METHODS = frozenset({"replace"})

# Filters that run a test on each item, named as a string: `select('search',
# 'light.')`, or `selectattr('entity_id', 'contains', 'light.kitchen')` with
# the attribute first. What a substring or pattern test looks for is text, the
# same as for `is search(...)`. #1838.
#
# `contains` only counts where the item is known to be a string. On a state
# object's `entity_id`, `state` or the like it is a substring test; on a list, like a group's
# `attributes.entity_id`, it asks whether a real entity is a member, and that
# is a reference. Plain `select` and `reject` do not say what their items are.
_SELECT_FILTERS = frozenset({"reject", "select"})
_SELECTATTR_FILTERS = frozenset({"rejectattr", "selectattr"})
_SELECT_TEXT_TESTS = frozenset({"match", "search"})
_STRING_ATTRIBUTES = frozenset({"domain", "entity_id", "name", "object_id", "state"})

# Only ever used to lex, never to render, so autoescaping has nothing to do.
_JINJA_LEXER = Environment(autoescape=True)

_OPENING_BRACKETS = frozenset("([{")

# Brackets that are not a call: parentheses that only group a value, and
# whatever builds a list, a dict or a tuple. A grouping bracket that meets a
# comma turns out to be a tuple.
_GROUP = "group"
_COLLECTION = "collection"

type _Bracket = bool | _SelectCall | str
_CLOSING_BRACKETS = frozenset(")]}")

_LINE_ENDINGS = re.compile(r"\r\n?")


@dataclass(slots=True)
class _SelectCall:
    """A select-style filter call, and what its arguments said so far."""

    with_attribute: bool
    argument: int = 0
    attribute: str | None = None
    test: str | None = None

    def is_text(self, argument: int) -> bool:
        """Return if the literal at this argument is text to look for."""
        offset = 1 if self.with_attribute else 0
        if argument != offset + 1 or self.test is None:
            return False

        if not self.with_attribute:
            return self.test in _SELECT_TEXT_TESTS

        return self.test in _SELECT_TEXT_TESTS or (
            self.test == "contains" and self.attribute in _STRING_ATTRIBUTES
        )

    def remember(self, literal: str) -> None:
        """Keep the attribute and test names, read off their literals."""
        offset = 1 if self.with_attribute else 0
        if self.with_attribute and self.argument == 0:
            self.attribute = literal
        elif self.argument == offset:
            self.test = literal


def _select_call(significant: deque[tuple[str, str]]) -> _SelectCall | None:
    """Return a tracker if the tokens before a `(` name a select-style filter."""
    *earlier, (_kind, name) = significant
    if not earlier or earlier[-1] != ("operator", "|"):
        return None

    if name in _SELECT_FILTERS:
        return _SelectCall(with_attribute=False)
    if name in _SELECTATTR_FILTERS:
        return _SelectCall(with_attribute=True)
    return None


def _is_text_call(significant: deque[tuple[str, str]]) -> bool:
    """Return if the tokens just before a `(` name a text filter, test or method.

    The name is the last token; what comes before it says how it is called.
    """
    *earlier, (_kind, name) = significant
    before = earlier[-1] if earlier else None

    if before == ("operator", "|"):
        return name in _TEXT_ARGUMENT_FILTERS
    if before == ("operator", "."):
        return name in _TEXT_ARGUMENT_METHODS
    if before == ("name", "not") and len(earlier) > 1:
        before = earlier[-2]
    return before == ("name", "is") and name in _TEXT_ARGUMENT_TESTS


def _track_brackets(
    open_brackets: list[_Bracket],
    significant: deque[tuple[str, str]],
    operator: str,
) -> None:
    """Open, close or step through the brackets an operator token touches."""
    if operator in _OPENING_BRACKETS:
        is_call = operator == "(" and bool(significant) and significant[-1][0] == "name"
        if is_call:
            open_brackets.append(
                _select_call(significant) or _is_text_call(significant)
            )
        else:
            open_brackets.append(_GROUP if operator == "(" else _COLLECTION)
    elif operator in _CLOSING_BRACKETS:
        if open_brackets:
            open_brackets.pop()
    elif operator == "," and open_brackets:
        # Only a comma right inside a select-style call moves on to its next
        # argument; one inside a list or a nested call belongs to that.
        if isinstance(innermost := open_brackets[-1], _SelectCall):
            innermost.argument += 1
        elif innermost == _GROUP:
            open_brackets[-1] = _COLLECTION


def _is_text_literal(open_brackets: list[_Bracket], literal: str) -> bool:
    """Return if a string literal is text for the call it is inside of."""
    calls = [
        (index, bracket)
        for index, bracket in enumerate(open_brackets)
        if not isinstance(bracket, str)
    ]
    if not calls:
        return False

    index, innermost_call = calls[-1]
    if not isinstance(innermost_call, _SelectCall):
        return bool(innermost_call)

    # Only a literal that is one of the call's arguments counts: parentheses
    # that only group it change nothing, a list or a tuple around it does.
    if _COLLECTION in open_brackets[index + 1 :]:
        return False

    is_text = innermost_call.is_text(innermost_call.argument)
    innermost_call.remember(literal[1:-1])
    return is_text


def _text_argument_offsets(template_str: str) -> frozenset[int]:
    """Return where each string literal passed to a text function starts.

    Jinja's own lexer does the reading, so quotes, escaped quotes and
    delimiters inside a string are all handled the way Jinja handles them.
    Its tokens come back raw, whitespace and prose included, so adding up
    their lengths gives each token's offset in the template. That only holds
    with plain newlines, which the lexer turns every line ending into, so the
    caller hands this a template that already has them.

    Only the innermost call counts, which is the one a literal is an argument
    of: in `replace(states('sensor.a'), ...)` the literal belongs to `states`,
    and that one is a reference. Plain grouping brackets are not a call and
    are looked through.

    A template Jinja cannot read yields nothing, and its literals are
    treated as they were before: as references.
    """
    offsets: set[int] = set()
    # Per open bracket: True for a text call, a tracker for a select-style
    # call, False for any other call, or what kind of bracket it is otherwise.
    open_brackets: list[_Bracket] = []
    # The last few tokens, enough to tell `x | replace(` from `x is match(`.
    significant: deque[tuple[str, str]] = deque(maxlen=3)
    offset = 0

    try:
        tokens = list(_JINJA_LEXER.lex(template_str))
    except TemplateSyntaxError:
        return frozenset()

    for _lineno, kind, value in tokens:
        token_start = offset
        offset += len(value)

        if kind == "whitespace":
            continue

        if kind == "operator":
            _track_brackets(open_brackets, significant, value)
        elif kind == "string" and _is_text_literal(open_brackets, value):
            offsets.add(token_start)
        elif kind in ("variable_end", "block_end"):
            open_brackets.clear()

        significant.append((kind, value))

    return frozenset(offsets)


def _is_text_argument_match(
    match: re.Match[str], text_argument_offsets: frozenset[int]
) -> bool:
    """Return if an entity-like literal is an argument to a text function."""
    groups = match.groups()
    if len(groups) == _STATES_DOMAIN_ENTITY_GROUPS:
        return False

    # Step back over the opening quote, which is not part of the capture.
    return match.span(1)[0] - 1 in text_argument_offsets


# The functions that look an entity up through `hass.states.get`, which tries
# the entity ID in lower case too: `states('sensor.Pump')` reads
# `sensor.pump`. The registry lookups (`device_id`, `area_id` and friends) do
# not, so for those a mixed case ID is no entity at all. Neither does
# `distance`, which takes an invalid entity ID for a coordinate.
_STATE_LOOKUPS = frozenset(
    {
        "closest",
        "expand",
        "has_value",
        "is_state",
        "is_state_attr",
        "state_attr",
        "state_attr_translated",
        "state_translated",
        "states",
    }
)


# The ones Home Assistant offers as a filter, where the entity is the value in
# front of it, and as a test, where it is the value tested. `is_state` is no
# filter, `states` no test.
_STATE_LOOKUP_FILTERS = frozenset(
    {
        "closest",
        "expand",
        "has_value",
        "state_attr",
        "state_attr_translated",
        "state_translated",
        "states",
    }
)
_STATE_LOOKUP_TESTS = frozenset({"has_value", "is_state", "is_state_attr"})

# The lookups that take more than one entity, and lists of them: `expand`,
# and `closest`, which hands its entities to `expand`.
_EXPANDING_LOOKUPS = frozenset({"closest", "expand"})

_SIGNS = frozenset({"add", "sub"})

# What a value can end with. A `+` or `-` right after one adds or subtracts,
# and the filter after it applies to what follows only: in
# `10 - 'sensor.a' | states`, `states` gets the literal. Anywhere else, at the
# start, after another operator, a bracket, a comma or a keyword, it is a sign.
_ENDS_A_VALUE = frozenset(
    {"float", "integer", "rbrace", "rbracket", "rparen", "string"}
)
# The names that are no value: what Jinja expects a value after.
_KEYWORDS = frozenset({"and", "do", "elif", "else", "if", "in", "is", "not", "or"})

# With this many arguments, `closest` takes the first two for a latitude and
# a longitude, and only the third is looked up.
_CLOSEST_WITH_COORDINATES = 3

_OPENERS = frozenset({"lbrace", "lbracket", "lparen"})
_CLOSERS = frozenset({"rbrace", "rbracket", "rparen"})


def _call_arguments(tokens: list[_Token], start: int) -> list[list[_Token]] | None:
    """Return the tokens of each argument of the call opened at this index.

    Split on the commas of the call itself; one inside a list or a nested
    call belongs to that.
    """
    if not _is(tokens, start, "lparen"):
        return None

    arguments: list[list[_Token]] = [[]]
    depth = 0
    for kind, value in tokens[start + 1 :]:
        if kind in _CLOSERS and depth == 0:
            # A trailing comma leaves nothing after it.
            return [argument for argument in arguments if argument]

        if kind in _OPENERS:
            depth += 1
        elif kind in _CLOSERS:
            depth -= 1
        elif kind == "comma" and depth == 0:
            arguments.append([])
            continue
        arguments[-1].append((kind, value))

    return None


def _group_end(tokens: list[_Token], start: int) -> int | None:
    """Return where the parentheses opened at this index close, if they group.

    With a comma of their own inside, they make a tuple instead.
    """
    depth = 0
    for position in range(start, len(tokens)):
        kind = tokens[position][0]
        if kind in _OPENERS:
            depth += 1
        elif kind in _CLOSERS:
            depth -= 1
            if depth == 0:
                return position
        elif kind == "comma" and depth == 1:
            return None
    return None


def _ungrouped(value: list[_Token]) -> list[_Token]:
    """Return a value without the parentheses that only group it.

    `('light.a')` is the text itself, the same as `'light.a'`.
    """
    while _is(value, 0, "lparen") and _group_end(value, 0) == len(value) - 1:
        value = value[1:-1]
    return value


def _literal(argument: list[_Token]) -> list[str]:
    """Return the entity ID an argument is, if it is one whole literal."""
    argument = _ungrouped(argument)
    if len(argument) == 1 and argument[0][0] == "string":
        return [argument[0][1]]
    return []


def _expanded(argument: list[_Token]) -> list[str]:
    """Return the entity IDs `expand` looks up from one argument.

    A literal, or a list or a tuple of nothing but literals, which `expand`
    looks into: it goes through anything it can iterate over.
    """
    if literal := _literal(argument):
        return literal

    argument = _ungrouped(argument)
    listed = _literals_listed(argument, 0)
    if listed is None or listed[1] != len(argument):
        return []
    return listed[0]


def _is_keyword(argument: list[_Token]) -> bool:
    """Return whether an argument is passed by keyword, or as `**` keywords."""
    return _shaped(argument, 0, ("name", "assign")) or _is(argument, 0, "pow")


def _is_positional(argument: list[_Token]) -> bool:
    """Return whether an argument takes one position: no keyword, no `*`."""
    return not (_is_keyword(argument) or _is(argument, 0, "mul"))


def _expand_arguments(arguments: list[list[_Token]]) -> list[str]:
    """Return the entity IDs `expand` looks up from its arguments.

    `expand` takes no keywords; with one, the call fails before it looks up
    anything. A `*` only adds more positions, which leaves the others be.
    """
    if any(_is_keyword(argument) for argument in arguments):
        return []
    return [entity for argument in arguments for entity in _expanded(argument)]


def _closest_arguments(arguments: list[list[_Token]]) -> list[str]:
    """Return the entity IDs `closest` looks up from its arguments.

    With one argument, those are the entities. With two, the first is the
    point it measures from, which is looked up as well. With three, the
    first two are a latitude and a longitude.
    """
    if not all(_is_positional(argument) for argument in arguments):
        return []

    if len(arguments) >= _CLOSEST_WITH_COORDINATES:
        return _expanded(arguments[2])

    found: list[str] = []
    if len(arguments) == _CLOSEST_WITH_COORDINATES - 1:
        found += _literal(arguments[0])
    if arguments:
        found += _expanded(arguments[-1])
    return found


def _called_lookup(tokens: list[_Token], index: int, name: str) -> list[str]:
    """Return what a lookup called by its name, `states(...)`, looks up."""
    if name in _EXPANDING_LOOKUPS:
        if (arguments := _call_arguments(tokens, index + 1)) is None:
            return []
        if name == "closest":
            return _closest_arguments(arguments)
        return _expand_arguments(arguments)

    # Only a whole argument: `'sensor.Pump' + '_interval'` and two strings
    # side by side are pieces of one.
    if _shaped(tokens, index + 1, ("lparen", "string")) and _ends_argument(
        tokens, index + 3
    ):
        return [tokens[index + 2][1]]
    if name == "states" and _shaped(tokens, index + 1, ("dot", "name", "dot", "name")):
        return [f"{tokens[index + 2][1]}.{tokens[index + 4][1]}"]
    return []


def _value_in_front(tokens: list[_Token], end: int, *, lists: bool) -> list[str]:
    """Return the literal, or the list of literals, right before this index.

    Parentheses that only group it change nothing. Only when it is all that
    a filter or a test there applies to.
    """
    if _is(tokens, end - 1, "string"):
        start = end - 1
    elif tokens[end - 1 : end] and tokens[end - 1][0] in {"rbracket", "rparen"}:
        if (opened := _opening_of(tokens, end - 1)) is None:
            return []
        start = opened
    else:
        return []

    if _takes_the_value(tokens, start):
        return []

    value = tokens[start:end]
    if (literal := _literal(value)) or not lists:
        return literal
    return _expanded(value)


def _opening_of(tokens: list[_Token], close: int) -> int | None:
    """Return where the bracket that closes at this index was opened."""
    depth = 0
    for position in range(close, -1, -1):
        kind = tokens[position][0]
        if kind in _CLOSERS:
            depth += 1
        elif kind in _OPENERS:
            depth -= 1
            if depth == 0:
                return position
    return None


def _takes_the_value(tokens: list[_Token], start: int) -> bool:
    """Return whether what comes right before a value takes it first.

    A string right before a string is glued to it. A sign takes the value
    before a filter does: `-'sensor.a' | states`. And a bracket right after a
    value calls it or picks from it: `f('sensor.a')`, `x['sensor.a']`.
    """
    if start == 0:
        return False

    kind, value = tokens[start - 1]
    if kind in _SIGNS:
        return _is_sign(tokens, start - 1)
    if tokens[start][0] == "string":
        return kind == "string"
    if kind == "name":
        return value not in _KEYWORDS
    return kind in _ENDS_A_VALUE


def _is_sign(tokens: list[_Token], index: int) -> bool:
    """Return whether the `+` or `-` at this index is a sign, not a sum."""
    if index == 0:
        return True

    kind, value = tokens[index - 1]
    if kind == "name":
        return value in _KEYWORDS
    return kind not in _ENDS_A_VALUE


def _filtered_lookup(tokens: list[_Token], index: int, name: str) -> list[str]:
    """Return what a lookup used as a filter, `'x' | states`, looks up.

    The value in front is the first argument. `expand` and `closest` take a
    list there too, and look up arguments of the filter as well. A dotted
    name, `| states.x`, is another filter.
    """
    if name not in _STATE_LOOKUP_FILTERS or _is(tokens, index + 1, "dot"):
        return []

    if name not in _EXPANDING_LOOKUPS:
        return _value_in_front(tokens, index - 1, lists=False)

    # Without parentheses, the filter has no arguments of its own. The value
    # in front is passed with them, so a keyword, which neither takes, makes
    # the call fail before it looks up anything.
    arguments = _call_arguments(tokens, index + 1) or []
    if any(_is_keyword(argument) for argument in arguments):
        return []

    in_front = _value_in_front(tokens, index - 1, lists=True)
    if name == "expand":
        return in_front + _expand_arguments(arguments)
    return _closest_filtered(in_front, arguments)


def _closest_filtered(in_front: list[str], arguments: list[list[_Token]]) -> list[str]:
    """Return what `closest` as a filter looks up.

    It moves the value in front to the end of its arguments. Behind three or
    more, the third is the one looked up, and the value in front is not.
    """
    if not all(_is_positional(argument) for argument in arguments):
        return []
    if len(arguments) >= _CLOSEST_WITH_COORDINATES:
        return _expanded(arguments[2])
    if len(arguments) == 1:
        return in_front + _literal(arguments[0])
    return in_front


def _tested_lookup(tokens: list[_Token], index: int, name: str) -> list[str]:
    """Return what a lookup used as a test, `'x' is has_value`, looks up.

    A dotted name, `is has_value.x`, is another test.
    """
    if name not in _STATE_LOOKUP_TESTS or _is(tokens, index + 1, "dot"):
        return []

    is_index = index - 2 if _is(tokens, index - 1, "name", "not") else index - 1
    return _value_in_front(tokens, is_index, lists=False)


@lru_cache(maxsize=1024)
def _looked_up_in_any_case(template_str: str) -> frozenset[str]:
    """Return the entity IDs a template looks a state up for, as written.

    Read with Jinja's own lexer, so only a real lookup counts: inside an
    expression, not in a string or in the text around it, by the very name
    (`STATES(...)`, `my_states(...)` and `obj.states(...)` are no lookups),
    and not called by a name the template defines itself. Called, as a
    filter or as a test, wherever Home Assistant offers it as one. These are the ones Home
    Assistant tries in lower case too.
    """
    expressions = _expressions(template_str)
    local = _named_locally(expressions)

    found: set[str] = set()
    for tokens in expressions:
        for index, (kind, name) in enumerate(tokens):
            if (
                kind != "name"
                or name not in _STATE_LOOKUPS
                or _is(tokens, index - 1, "dot")
            ):
                continue

            # Filters and tests are Jinja's own registries: a name the
            # template defines does not hide one, it only hides a function.
            if _is(tokens, index - 1, "pipe"):
                found.update(_filtered_lookup(tokens, index, name))
            elif _is_test(tokens, index):
                found.update(_tested_lookup(tokens, index, name))
            elif name not in local:
                found.update(_called_lookup(tokens, index, name))
    return frozenset(found)


def _entity_id_from_template_match(match: re.Match[str]) -> str:
    """Return the entity ID captured by a template regex match."""
    groups = match.groups()

    # Handle the states.domain.entity pattern that captures (domain, object_id)
    if len(groups) == _STATES_DOMAIN_ENTITY_GROUPS:
        return f"{groups[0]}.{groups[1]}"

    return groups[0]


@lru_cache(maxsize=1024)
def _extract_entity_candidates_from_template(template_str: str) -> frozenset[str]:
    """Extract entity ID candidates from a template string.

    Pure in the template string, so results are cached: repairs re-inspect
    the same unchanged templates over and over.
    """
    # One kind of line ending, so the lexer's offsets and the regex's agree.
    template_without_comments = _LINE_ENDINGS.sub(
        "\n", _strip_jinja_comments(template_str)
    )
    text_argument_offsets = _text_argument_offsets(template_without_comments)

    entities = set()

    for pattern in COMPILED_ENTITY_ID_TEMPLATE_PATTERNS:
        for match in pattern.finditer(template_without_comments):
            if (
                _is_concatenated_template_match(template_without_comments, match)
                or _is_jinja_import_match(template_without_comments, match)
                or _is_string_method_argument_match(template_without_comments, match)
                or _is_text_argument_match(match, text_argument_offsets)
            ):
                continue

            entity_id = _entity_id_from_template_match(match)
            if not entity_id.islower() and entity_id in _looked_up_in_any_case(
                template_without_comments
            ):
                entity_id = entity_id.lower()

            # For each entity ID (which might be comma-separated), add all valid ones
            for individual_id in split_comma_separated_entity_ids(entity_id):
                if individual_id.startswith(NEVER_AN_ENTITY_PREFIXES):
                    continue
                if valid_entity_id(individual_id):
                    entities.add(individual_id)

    return frozenset(entities)


def extract_entities_from_template_regex(
    hass: HomeAssistant,
    template_str: str,
    known_services: set[str] | None = None,
) -> set[str]:
    """Extract entity IDs from template string using regex patterns.

    This function uses regex patterns based on Home Assistant's core validation
    patterns to find entity IDs referenced in template functions. It's designed
    to complement the RenderInfo analysis by catching entities that might be
    missed by template parsing.
    """
    if not isinstance(template_str, str):
        return set()

    entities = set(_extract_entity_candidates_from_template(template_str))

    # Filter out known services to avoid false positives
    if known_services is None:
        known_services = async_get_all_services(hass)
    return entities - known_services


async def _process_template_object(
    hass: HomeAssistant,
    template: Template,
    known_entity_ids: set[str],
    known_services: set[str],
    unknown_entities: set[str],
) -> None:
    """Process a Template object and add unknown entities to the set."""
    template_entities = set()

    # Use regex patterns on the template string
    try:
        if hasattr(template, "template") and template.template:
            regex_entities = extract_entities_from_template_regex(
                hass, template.template, known_services
            )
            template_entities.update(regex_entities)
    # pylint: disable-next=broad-exception-caught
    except Exception:  # noqa: BLE001
        LOGGER.debug("Error in regex entity extraction for Template object")

    # Check if any of the template entities are unknown
    for template_entity in template_entities:
        if template_entity not in known_entity_ids:
            unknown_entities.add(template_entity)


async def _process_template_string(
    hass: HomeAssistant,
    template_str: str,
    known_entity_ids: set[str],
    known_services: set[str],
    unknown_entities: set[str],
) -> None:
    """Process a template string and add unknown entities to the set."""
    template_entities = await async_extract_entities_from_template_string(
        hass, template_str, known_services
    )
    # Check if any of the template entities are unknown
    for template_entity in template_entities:
        # Handle comma-separated entity lists
        for entity_id in split_comma_separated_entity_ids(template_entity):
            if (
                entity_id not in known_entity_ids
                and valid_entity_id(entity_id)
                and not entity_id.startswith(IGNORED_ENTITY_DOMAINS)
            ):
                unknown_entities.add(entity_id)


async def async_filter_known_entity_ids_with_templates(
    hass: HomeAssistant,
    entity_ids: Iterable[str],
    known_entity_ids: set[str] | None = None,
    known_services: set[str] | None = None,
) -> set[str]:
    """Async version that can process templates to extract entity dependencies.

    This function processes both regular entity IDs and template strings,
    extracting entity dependencies from templates using RenderInfo. Names that
    belong to an existing action are dropped, since those are not entities.

    ``known_services`` is what tells an action name apart from an entity id.
    Building it flattens every service Home Assistant has, so a caller running
    this over one item after another should build it once and pass it in.
    """
    if known_entity_ids is None:
        known_entity_ids = async_get_all_entity_ids(hass)

    unknown_entities = set()

    for entity_id_raw in entity_ids:
        # Handle Template objects
        if isinstance(entity_id_raw, Template):
            if known_services is None:
                known_services = async_get_all_services(hass)
            await _process_template_object(
                hass, entity_id_raw, known_entity_ids, known_services, unknown_entities
            )
            continue

        if not isinstance(entity_id_raw, str):
            continue

        # Check if this looks like a template string
        if is_template_string(entity_id_raw):
            if known_services is None:
                known_services = async_get_all_services(hass)
            await _process_template_string(
                hass, entity_id_raw, known_entity_ids, known_services, unknown_entities
            )
        else:
            # Process as regular entity ID(s), handling comma-separated lists
            for entity_id in split_comma_separated_entity_ids(entity_id_raw):
                if (
                    not entity_id.startswith(NEVER_AN_ENTITY_PREFIXES)
                    and not entity_id.startswith(IGNORED_ENTITY_DOMAINS)
                    and entity_id not in known_entity_ids
                    and valid_entity_id(entity_id)
                ):
                    # Process as regular entity ID
                    unknown_entities.add(entity_id)

    return async_drop_existing_action_names(hass, unknown_entities)


def extract_template_strings_from_config(
    config: Any, strings: list[str] | None = None
) -> list[str]:
    """Recursively extract template strings from configuration data."""
    if strings is None:
        strings = []

    if isinstance(config, str):
        if is_template_string(config):  # Uses the util's is_template_string
            strings.append(config)
    elif isinstance(config, dict):
        for value in config.values():
            extract_template_strings_from_config(value, strings)
    elif isinstance(config, (list, tuple)):
        for item in config:
            extract_template_strings_from_config(item, strings)
    return strings


async def async_extract_entities_from_config(
    hass: HomeAssistant,
    config: Any,
    known_services: set[str] | None = None,
) -> set[str]:
    """Extract entity IDs referenced in templates within a configuration structure.

    ``known_services`` is what tells an action name apart from an entity id.
    Building it flattens every service Home Assistant has, so a caller walking
    one configuration after another should build it once and pass it in.
    """
    entities = set()
    if not config:
        return entities

    template_strings = extract_template_strings_from_config(config)
    if known_services is None:
        known_services = async_get_all_services(hass) if template_strings else set()
    extracted_templates: dict[str, set[str]] = {}
    for template_str in template_strings:
        try:
            # async_extract_entities_from_template_string already handles
            # TemplateError and other exceptions internally, logging them.
            if template_str not in extracted_templates:
                extracted_templates[
                    template_str
                ] = await async_extract_entities_from_template_string(
                    hass, template_str, known_services
                )
            referenced_entities = extracted_templates[template_str]
            entities.update(referenced_entities)
        # pylint: disable-next=broad-exception-caught
        except Exception as exc:  # noqa: BLE001 - Keep broad for unexpected issues
            # This catch is a safeguard; internal function should handle most.
            LOGGER.debug(
                "Unexpected error extracting entities from template string "
                "'%s...' in config: %s",
                template_str[:50],
                exc,  # Pass the exception for logging
            )
    return entities


# The functions, and filters, that read one attribute of one entity.
_ATTRIBUTE_FUNCTIONS = frozenset({"is_state_attr", "state_attr"})

# What may follow an argument for it to be the whole argument: the end of the
# call, or the next argument. Anything else, like `~`, makes it a piece of one.
_ARGUMENT_ENDS = frozenset({"comma", "rparen"})

# What reading the attributes as a mapping can mean other than an attribute.
# Jinja finds the method before it looks for a key: `.attributes.items` is
# the method, called or not.
_MAPPING_METHODS = frozenset(name for name in dir(dict) if not name.startswith("_"))

# What comes right after a parameter of a macro or call block: the next one,
# the end of them, or its default.
_PARAMETER_ENDS = frozenset({"assign", "comma", "rparen"})

# Where an expression starts and ends; everything else is template text.
_EXPRESSION_STARTS = frozenset({"block_begin", "variable_begin"})
_EXPRESSION_ENDS = frozenset({"block_end", "variable_end"})

type _Token = tuple[str, str]


def _expressions(template_str: str) -> list[list[_Token]]:
    """Return the tokens of each expression in a template, read by Jinja.

    Template text around the expressions, comments and whitespace are not in
    them. A template Jinja cannot read has none.
    """
    expressions: list[list[_Token]] = []
    current: list[_Token] | None = None
    try:
        for token in _JINJA_LEXER.lexer.tokenize(template_str):
            if token.type in _EXPRESSION_STARTS:
                current = []
            elif token.type in _EXPRESSION_ENDS:
                if current:
                    expressions.append(current)
                current = None
            elif current is not None:
                current.append((token.type, token.value))
    except TemplateSyntaxError:
        return []

    return expressions


def _is(tokens: list[_Token], index: int, kind: str, value: str | None = None) -> bool:
    """Return whether the token at this index is of this kind, and value."""
    if not 0 <= index < len(tokens):
        return False
    token_kind, token_value = tokens[index]
    return token_kind == kind and (value is None or token_value == value)


def _shaped(
    tokens: list[_Token], start: int, shape: tuple[str | tuple[str, str], ...]
) -> bool:
    """Return whether the tokens from here on have this shape.

    Each part is a token kind, or a kind and the value it must have.
    """
    return all(
        _is(tokens, start + offset, *(part if isinstance(part, tuple) else (part,)))
        for offset, part in enumerate(shape)
    )


def _ends_argument(tokens: list[_Token], index: int) -> bool:
    """Return whether the token at this index ends an argument."""
    return index < len(tokens) and tokens[index][0] in _ARGUMENT_ENDS


def _function_pair(tokens: list[_Token], index: int) -> tuple[str, str] | None:
    """Read `state_attr('light.x', 'brightness')` starting at its name."""
    if (
        _is(tokens, index - 1, "dot")
        or _is(tokens, index - 1, "pipe")
        or not _shaped(tokens, index + 1, ("lparen", "string", "comma", "string"))
        or not _ends_argument(tokens, index + 5)
    ):
        return None
    return tokens[index + 2][1], tokens[index + 4][1]


def _filter_pair(tokens: list[_Token], index: int) -> tuple[str, str] | None:
    """Read `'light.x' | state_attr('brightness')` starting at its name."""
    if (
        not _is(tokens, index - 1, "pipe")
        or not _is(tokens, index - 2, "string")
        or not _is(tokens, index + 1, "lparen")
        or not _is(tokens, index + 2, "string")
        or not _ends_argument(tokens, index + 3)
    ):
        return None
    return tokens[index - 2][1], tokens[index + 2][1]


def _states_pair(tokens: list[_Token], index: int) -> tuple[str, str] | None:
    """Read `states.light.x.attributes...` starting at `states`.

    The attribute as a name, `['brightness']` or `.get('brightness')`. A
    method on the attributes, like `.items()`, is not an attribute.
    """
    if _is(tokens, index - 1, "dot") or not _shaped(
        tokens, index + 1, ("dot", "name", "dot", "name", "dot", ("name", "attributes"))
    ):
        return None

    if (attribute := _attribute_after(tokens, index + 7)) is None:
        return None
    return f"{tokens[index + 2][1]}.{tokens[index + 4][1]}", attribute


def _attribute_after(tokens: list[_Token], after: int) -> str | None:
    """Read the attribute that follows `.attributes`, if it is a literal one."""
    if _is(tokens, after, "lbracket"):
        if _is(tokens, after + 1, "string") and _is(tokens, after + 2, "rbracket"):
            return tokens[after + 1][1]
        return None

    if not _is(tokens, after, "dot") or not _is(tokens, after + 1, "name"):
        return None

    name = tokens[after + 1][1]
    if not _is(tokens, after + 2, "lparen"):
        return None if name in _MAPPING_METHODS else name

    if (
        name == "get"
        and _is(tokens, after + 3, "string")
        and _ends_argument(tokens, after + 4)
    ):
        return tokens[after + 3][1]

    return None


def _names_defined(tokens: list[_Token]) -> set[str]:
    """Return the names one expression gives a meaning, like `{% set x = 1 %}`.

    Generous where it is cheap to be: a keyword argument counts as well.
    Taking a name for a local one only means a lookup that is not checked;
    missing one means a finding about a template that works.
    """
    statement = tokens[0][1] if _is(tokens, 0, "name") else None
    names = [
        (index, value) for index, (kind, value) in enumerate(tokens) if kind == "name"
    ]

    if statement == "for":
        # `{% for key, value in ... %}`: everything up to the `in`.
        loop_names: set[str] = set()
        for _index, value in names[1:]:
            if value == "in":
                break
            loop_names.add(value)
        return loop_names

    if statement in {"import", "from"}:
        # `{% import 'x' as name %}`, `{% from 'x' import a, b as c %}`.
        return {
            value
            for index, value in names
            if _is(tokens, index - 1, "name", "as")
            or _is(tokens, index - 1, "name", "import")
            or _is(tokens, index - 1, "comma")
        }

    if statement == "set" and not any(kind == "assign" for kind, _value in tokens):
        # `{% set name %}...{% endset %}`.
        return {value for _index, value in names[1:]}

    defined = {
        value
        for index, value in names
        # `{% set a, b = ... %}`, `{% with a = ... %}`, and the keywords.
        if _is(tokens, index + 1, "assign")
        or (statement == "set" and _is(tokens, index + 1, "comma"))
    }
    if statement in {"macro", "call"}:
        # `{% macro name(a, b=1) %}`, `{% call(a) other() %}`: the name, and
        # whatever is followed by what ends a parameter.
        defined.update(
            value
            for index, value in names
            if index == 1
            or (index + 1 < len(tokens) and tokens[index + 1][0] in _PARAMETER_ENDS)
        )
    return defined


def _named_locally(expressions: list[list[_Token]]) -> set[str]:
    """Return every name a template gives a meaning of its own, anywhere in it."""
    return {name for tokens in expressions for name in _names_defined(tokens)}


@lru_cache(maxsize=1024)
def extract_attribute_pairs_from_template(
    template_str: str,
    shadowed: frozenset[str] = frozenset(),
) -> frozenset[tuple[str, str]]:
    """Return the (entity ID, attribute) pairs a template names literally.

    Read by Jinja's own lexer, so only what is inside an expression counts,
    and only pairs where both are a whole string literal. An attribute built
    from pieces, like `'color_' ~ 'temp'`, or coming from a variable, is
    whatever it is at runtime, and guessing at that is how a repair ends up
    reporting a template that works. So is a call in a template that
    defines its own `states` or `state_attr`: then those are not Home
    Assistant's. The same goes for the names in `shadowed`, which the
    configuration around the template gives a meaning of its own. Neither
    hides the `state_attr` filter.

    Pure in its arguments, so cached like the entity extraction.
    """
    if not is_template_string(template_str):
        return frozenset()

    expressions = _expressions(template_str)
    named_locally = _named_locally(expressions) | shadowed

    pairs: set[tuple[str, str]] = set()
    for tokens in expressions:
        for index, (kind, value) in enumerate(tokens):
            if kind != "name":
                continue

            # Filters are Jinja's own registry: a name the template, or the
            # configuration, defines does not hide one, it only hides a function.
            if value in _ATTRIBUTE_FUNCTIONS and _is(tokens, index - 1, "pipe"):
                pair = _filter_pair(tokens, index)
            elif value in named_locally:
                continue
            elif value in _ATTRIBUTE_FUNCTIONS:
                pair = _function_pair(tokens, index)
            elif value == "states":
                pair = _states_pair(tokens, index)
            else:
                continue

            if pair is not None and valid_entity_id(pair[0]):
                pairs.add(pair)

    return frozenset(pairs)


# The function, and test, that compare the state of one entity.
_STATE_FUNCTION = "is_state"


def _states_argument(tokens: list[_Token], index: int) -> tuple[list[str], int] | None:
    """Read the states `is_state` compares to, starting at the argument.

    One literal, or a list of them, which core's `is_state` takes as well.
    Not a tuple: core only looks inside a list, so a tuple never matches.
    Returns the literals and where the argument ends.
    """
    if _is(tokens, index, "string"):
        return [tokens[index][1]], index + 1
    if _is(tokens, index, "lbracket"):
        return _literals_listed(tokens, index)

    # Parentheses around one thing only group it: `(['on'])` is still the
    # list. With a comma after it, `(['on'],)`, it is a tuple and not read.
    if _is(tokens, index, "lparen"):
        grouped = _states_argument(tokens, index + 1)
        if grouped is not None and _is(tokens, grouped[1], "rparen"):
            return grouped[0], grouped[1] + 1
    return None


def _function_pairs(tokens: list[_Token], index: int) -> set[tuple[str, str]]:
    """Read `is_state('light.x', 'on')` starting at its name.

    Also with a list of states, `is_state('light.x', ['on', 'off'])`.
    """
    if (
        _is(tokens, index - 1, "dot")
        or _is(tokens, index - 1, "pipe")
        or not _shaped(tokens, index + 1, ("lparen", "string", "comma"))
        or (states := _states_argument(tokens, index + 4)) is None
    ):
        return set()

    literals, end = states
    if not _ends_argument(tokens, end):
        return set()
    return {(tokens[index + 2][1], literal) for literal in literals}


def _test_pairs(tokens: list[_Token], index: int) -> set[tuple[str, str]]:
    """Read `'light.x' is is_state('on')` starting at its name.

    Also as `is not`, and with a list of states. Only with the states in
    parentheses: without them, where the state ends depends on what follows
    it.
    """
    subject = index - 2
    if _is(tokens, index - 1, "name", "not"):
        subject -= 1

    if (
        not _shaped(tokens, subject, ("string", ("name", "is")))
        or not _is(tokens, index + 1, "lparen")
        or (states := _states_argument(tokens, index + 2)) is None
    ):
        return set()

    literals, end = states
    if not _is(tokens, end, "rparen"):
        return set()

    # Jinja glues neighbouring strings into one, so a string right before is
    # only the end of the entity ID. And a sign right before can make the
    # test about the signed value: `-'light.x' is is_state('on')` tests the
    # negation. Telling a sign from a minus between two values is not worth
    # it for this.
    if subject > 0 and tokens[subject - 1][0] in {"string", *_SIGNS}:
        return set()
    return {(tokens[subject][1], literal) for literal in literals}


def _is_test(tokens: list[_Token], index: int) -> bool:
    """Return whether the name at this index is used as a test."""
    return _is(tokens, index - 1, "name", "is") or (
        _is(tokens, index - 1, "name", "not") and _is(tokens, index - 2, "name", "is")
    )


# Comparing two things is looser than anything but `not`, `and`, `or` and
# `if ... else` in Jinja (`parse_compare` sits right under `parse_not`), so
# a side is whole when what is around it is one of those, or something that
# opens or closes a part of the expression. Anything else around it, like a
# filter, `~`, maths, a method or another comparison, takes part of it.
_OPENS_A_SIDE = frozenset({"assign", "comma", "lbracket", "lparen"})
_CLOSES_A_SIDE = frozenset({"comma", "rbracket", "rparen"})
_KEYWORDS_BEFORE_A_SIDE = frozenset({"and", "elif", "else", "if", "not", "or"})
_KEYWORDS_AFTER_A_SIDE = frozenset({"and", "else", "if", "or"})

# Comparisons that hold a state to one literal.
_EQUALITY = frozenset({"eq", "ne"})

# How a list, or a tuple, of literals is closed.
_CLOSING = {"lbracket": "rbracket", "lparen": "rparen"}

# What reads the state of an entity in a template.
_STATES = "states"


def _side_starts(tokens: list[_Token], index: int) -> bool:
    """Return whether a side of a comparison can start at this index."""
    if index == 0:
        return True

    kind, value = tokens[index - 1]
    if kind in _OPENS_A_SIDE:
        return True
    # `is not` makes what follows a test, not a side.
    return (
        kind == "name"
        and value in _KEYWORDS_BEFORE_A_SIDE
        and not (value == "not" and _is(tokens, index - 2, "name", "is"))
    )


def _side_ends(tokens: list[_Token], index: int) -> bool:
    """Return whether a side of a comparison can end right before this index."""
    if index == len(tokens):
        return True

    kind, value = tokens[index]
    return kind in _CLOSES_A_SIDE or (
        kind == "name" and value in _KEYWORDS_AFTER_A_SIDE
    )


def _state_lookup(tokens: list[_Token], index: int) -> tuple[str, int] | None:
    """Read `states('light.x')` or `states.light.x.state` starting at `states`.

    Returns the entity ID and where the lookup ends. Only with nothing more
    in the call: `states('light.x', rounded=True)` is the state made pretty.
    """
    if _shaped(tokens, index + 1, ("lparen", "string", "rparen")):
        return tokens[index + 2][1], index + 4

    if _shaped(
        tokens, index + 1, ("dot", "name", "dot", "name", "dot", ("name", "state"))
    ):
        return f"{tokens[index + 2][1]}.{tokens[index + 4][1]}", index + 7

    return None


def _literals_listed(tokens: list[_Token], index: int) -> tuple[list[str], int] | None:
    """Read `['on', 'off']` or `('on', 'off')` starting at its bracket.

    Returns the literals and where the list ends. Parentheses around a
    single literal, without a comma, are no tuple but the text itself, and
    `in` a text looks for a piece of it.
    """
    if index >= len(tokens) or (closing := _CLOSING.get(tokens[index][0])) is None:
        return None

    literals: list[str] = []
    commas = 0
    position = index + 1
    while _is(tokens, position, "string"):
        literals.append(tokens[position][1])
        position += 1
        if not _is(tokens, position, "comma"):
            break
        commas += 1
        position += 1

    if not _is(tokens, position, closing) or (closing == "rparen" and not commas):
        return None
    return literals, position + 1


def _compared_after(tokens: list[_Token], index: int) -> tuple[list[str], int] | None:
    """Read what a state is compared to, starting right after the lookup.

    `== 'on'`, `!= 'on'`, and `in` or `not in` a list of literals. Returns
    the literals and where the comparison ends.
    """
    if index < len(tokens) and tokens[index][0] in _EQUALITY:
        if _is(tokens, index + 1, "string"):
            return [tokens[index + 1][1]], index + 2
        return None

    if _is(tokens, index, "name", "not"):
        index += 1
    if not _is(tokens, index, "name", "in"):
        return None
    return _literals_listed(tokens, index + 1)


def _comparison_pairs(tokens: list[_Token], index: int) -> set[tuple[str, str]]:
    """Read a state compared to literals, the lookup starting at `states`.

    The lookup first, `states('light.x') == 'on'`, or the literal first,
    `'on' == states('light.x')`, which only goes for `==` and `!=`: a text
    `in` a state looks for a piece of it.
    """
    if (lookup := _state_lookup(tokens, index)) is None:
        return set()
    entity_id, after = lookup

    if (
        _side_starts(tokens, index)
        and (compared := _compared_after(tokens, after)) is not None
    ):
        literals, end = compared
        if _side_ends(tokens, end):
            return {(entity_id, literal) for literal in literals}

    literal = index - 2
    if (
        _is(tokens, literal, "string")
        and index - 1 >= 0
        and tokens[index - 1][0] in _EQUALITY
        and _side_starts(tokens, literal)
        and _side_ends(tokens, after)
    ):
        return {(entity_id, tokens[literal][1])}

    return set()


@lru_cache(maxsize=1024)
def extract_state_pairs_from_template(
    template_str: str,
    shadowed: frozenset[str] = frozenset(),
) -> frozenset[tuple[str, str]]:
    """Return the (entity ID, state) pairs a template compares literally.

    `is_state('light.x', 'on')`, and the same as a test, `'light.x' is
    is_state('on')`; Home Assistant offers no filter for it. Both also with a
    list of states, `is_state('light.x', ['on', 'off'])`. And a state
    compared to literals: `states('light.x') == 'on'`, `!=`, the other way
    around, or `in` a list of them, also as `states.light.x.state`.

    Read like the attribute pairs: whole string literals, inside an
    expression, and not called in a template that defines its own
    `is_state` or `states`, or sits in a configuration that does
    (`shadowed`). Neither hides the `is_state` test. A comparison only when
    nothing else takes part in it: with a filter, `~` or anything else in
    between, what is compared is something else than the state.

    Pure in its arguments, so cached like the entity extraction.
    """
    if not is_template_string(template_str):
        return frozenset()

    expressions = _expressions(template_str)
    named_locally = _named_locally(expressions) | shadowed

    pairs: set[tuple[str, str]] = set()
    for tokens in expressions:
        for index, (kind, value) in enumerate(tokens):
            if kind != "name":
                continue

            # Tests are Jinja's own registry: a name the template, or the
            # configuration, defines does not hide one, it only hides a function.
            found: set[tuple[str, str]] = set()
            if value == _STATE_FUNCTION and _is_test(tokens, index):
                found = _test_pairs(tokens, index)
            elif value in named_locally:
                continue
            elif value == _STATE_FUNCTION:
                found = _function_pairs(tokens, index)
            elif value == _STATES:
                found = _comparison_pairs(tokens, index)

            pairs.update(pair for pair in found if valid_entity_id(pair[0]))

    return frozenset(pairs)


# The functions that take a device ID or an entity ID, called directly or as
# a filter. `is_device_attr` is a test as well.
_DEVICE_LOOKUPS = frozenset({"device_attr", "device_name", "is_device_attr"})
_DEVICE_LOOKUP_TESTS = frozenset({"is_device_attr"})


def _looked_up_devices(template_str: str) -> set[str]:
    """Return the literals a template hands a device lookup, as written.

    Read with Jinja's own lexer, like the state lookups: only a real call by
    the very name, not in a string or the text around it, not a method and
    not called by a name the template defines itself. An entity ID there is
    an entity reference, and anything else the lookup quietly turns into
    nothing, so only a literal shaped like a registry ID is a device.
    """
    expressions = _expressions(template_str)
    local = _named_locally(expressions)

    found: set[str] = set()
    for tokens in expressions:
        for index, (kind, name) in enumerate(tokens):
            if (
                kind != "name"
                or name not in _DEVICE_LOOKUPS
                or _is(tokens, index - 1, "dot")
            ):
                continue

            # As a filter or a test, the value right in front of it is the
            # device. Two strings side by side are joined into one by Jinja,
            # so then that one is only a piece of it. Filters and tests are
            # Jinja's own registries: a name the template defines does not
            # hide one, it only hides a function.
            if _is(tokens, index - 1, "pipe"):
                value = index - 2
            elif name in _DEVICE_LOOKUP_TESTS and _is_test(tokens, index):
                value = index - (3 if _is(tokens, index - 1, "name", "not") else 2)
            elif name in local:
                continue
            else:
                # Called, only a whole first argument.
                if _shaped(tokens, index + 1, ("lparen", "string")) and _ends_argument(
                    tokens, index + 3
                ):
                    found.add(tokens[index + 2][1])
                continue

            if _is(tokens, value, "string") and not _is(tokens, value - 1, "string"):
                found.add(tokens[value][1])

    return {value for value in found if is_device_id_shaped(value)}


@lru_cache(maxsize=1024)
def _extract_device_ids_from_template(template_str: str) -> frozenset[str]:
    """Extract device IDs referenced through the device functions in a template."""
    template_without_comments = _strip_jinja_comments(template_str)
    device_ids = set(_DEVICE_ENTITIES_PATTERN.findall(template_without_comments))
    device_ids.update(_looked_up_devices(template_str))

    return frozenset(device_ids)


def extract_device_ids_from_config(config: Any) -> set[str]:
    """Extract device IDs referenced through the device functions in templates."""
    device_ids: set[str] = set()
    for template_str in extract_template_strings_from_config(config):
        device_ids.update(_extract_device_ids_from_template(template_str))
    return device_ids
