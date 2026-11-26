"""Tests for the translated pages of the documentation.

A machine writes the pages under `documentation/translations/output/`, one
directory per language. Nobody reads every one of them, so these tests hold
what a reader, and a released version of Spook, depends on.

Every "learn more" link in a repair points at an anchor, and the site sends a
reader in another language to the same anchor on the translated page. So a
translated page has the anchors of the English page: all of them, in order.
The rest is what a translation never gets to change: the code, the links,
the components and the screenshots.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest
import yaml

from tests.documentation_helpers import CONTENT, headings

if TYPE_CHECKING:
    from pathlib import Path

OUTPUT = CONTENT.parent / "translations" / "output"

PAGES = sorted(OUTPUT.glob("*/content/**/*.md"))

_FRONT_MATTER = re.compile(r"^---\n(.*?\n)---\n", re.DOTALL)
_CODE = re.compile(r"^[ \t]*```.*?^[ \t]*```", re.MULTILINE | re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_LINK = re.compile(r"\]\((<[^>]*>|[^()\s]*)\)")
_COMPONENT = re.compile(r"^\s*(:+[a-z][a-z0-9-]*)(?:\{(.*)\})?\s*$", re.MULTILINE)
_TERM = re.compile(r":term\[([^\]]*)\](?:\{to=\"([^\"]*)\"\})?")
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)

# The front matter a translation rewrites. Everything else is the site's.
_TEXT_KEYS = ("title", "description", "subtitle")

# The component props a translation rewrites.
_TEXT_PROPS = re.compile(r'\b(label|title|alt)="[^"]*"')


def _name(path: Path) -> str:
    """Name a translated page in the test output, like `nl/automation`."""
    language = path.relative_to(OUTPUT).parts[0]
    return f"{language}/{path.stem.split('.', 1)[-1]}"


def _english(path: Path) -> Path:
    """Return the English page a translated page was made from."""
    return CONTENT.joinpath(*path.relative_to(OUTPUT).parts[2:])


def _front_matter(text: str) -> dict:
    """Return the front matter of a page."""
    found = _FRONT_MATTER.match(text)
    assert found, "the page has no front matter"
    return yaml.safe_load(found.group(1))


def _prose(text: str) -> str:
    """Return a page without its front matter and its code blocks."""
    return _CODE.sub("", _FRONT_MATTER.sub("", text, count=1))


def _components(text: str) -> list[str]:
    """Return every component of a page, without the text in its props."""
    return [
        f"{name} {_TEXT_PROPS.sub(r'\1', props or '')}".strip()
        for name, props in _COMPONENT.findall(_prose(text))
    ]


def _terms(text: str) -> list[str]:
    """Return the glossary entry every term on a page links to, sorted.

    Without a `to`, a term links to the entry of the word it shows. A sentence
    is free to put its words in another order, so the order is not compared.
    """
    return sorted((key or shown).lower() for shown, key in _TERM.findall(_prose(text)))


def test_the_translated_pages_do_not_pose_as_english_ones() -> None:
    """The other documentation tests find pages by globbing `content/`."""
    assert not [path for path in CONTENT.rglob("*.md") if OUTPUT in path.parents]
    assert not list(CONTENT.rglob("*.lock.json"))


@pytest.mark.parametrize("path", PAGES, ids=_name)
def test_a_translated_page_has_an_english_page(path: Path) -> None:
    """A page that lost its English source would never be updated again."""
    assert _english(path).is_file()


@pytest.mark.parametrize("path", PAGES, ids=_name)
def test_a_translated_page_says_it_is_generated(path: Path) -> None:
    """Whoever opens the file has to learn not to edit it, and where to go."""
    lines = path.read_text().split("\n")
    assert lines[0] == "---"
    assert lines[1].startswith("# GENERATED FILE. Do not edit")
    assert _english(path).relative_to(CONTENT.parents[1]).as_posix() in lines[2]

    lock = json.loads(path.with_name(f"{path.stem}.lock.json").read_text())
    assert next(iter(lock)) == "//"
    assert lock["sections"]
    assert all(section["model"] and section["date"] for section in lock["sections"])


@pytest.mark.parametrize("path", PAGES, ids=_name)
def test_a_translated_page_has_the_english_anchors(path: Path) -> None:
    """Released versions of Spook link to these anchors, in every language."""
    english = [
        (level, anchor) for level, _, anchor in headings(_english(path).read_text())
    ]
    translated = [(level, anchor) for level, _, anchor in headings(path.read_text())]

    assert translated == english


@pytest.mark.parametrize("path", PAGES, ids=_name)
def test_a_translated_heading_spells_out_its_anchor(path: Path) -> None:
    """A translated heading would otherwise get an anchor in its own language."""
    for line in re.findall(r"^#{2,6} .+$", _prose(path.read_text()), re.MULTILINE):
        assert re.search(r" \{#[a-z0-9-]+\}$", line), line


@pytest.mark.parametrize("path", PAGES, ids=_name)
def test_a_translated_page_keeps_the_front_matter(path: Path) -> None:
    """The address of a page and how it is listed are not text to translate."""
    english = _front_matter(_english(path).read_text())
    translated = _front_matter(path.read_text())

    assert translated["path"] == english["path"]
    assert set(translated) == set(english)

    for key in _TEXT_KEYS:
        if key in english:
            assert isinstance(translated[key], str)
            assert translated[key].strip()
            assert "\n" not in translated[key].strip()

    # The site reads up to the first colon and space in some places.
    assert ": " not in translated.get("description", "")

    for data in (english, translated):
        for key in _TEXT_KEYS:
            data.pop(key, None)
        if isinstance(data.get("navigation"), dict):
            data["navigation"].pop("title", None)
    assert translated == english


@pytest.mark.parametrize("path", PAGES, ids=_name)
def test_a_translated_page_keeps_what_is_not_text(path: Path) -> None:
    """Code, links, components and tables come through as they went in."""
    english = _english(path).read_text()
    translated = path.read_text()

    assert "⟦" not in translated
    assert "⟧" not in translated

    # Code blocks and examples: the same, in the same order.
    assert _CODE.findall(translated) == _CODE.findall(english)

    # Inline code: the same spans, wherever the sentence puts them.
    assert sorted(_INLINE_CODE.findall(_prose(translated))) == sorted(
        _INLINE_CODE.findall(_prose(english))
    )

    # Links and images: the same targets, in the same order.
    assert _LINK.findall(_prose(translated)) == _LINK.findall(_prose(english))

    # Components: the same ones, with the same names, icons and screenshots.
    assert _components(translated) == _components(english)

    # Terms: still pointing at the English glossary entries.
    assert _terms(translated) == _terms(english)

    # Tables: the same rows, with the same number of cells.
    def shape(text: str) -> list[int]:
        return [
            len(re.split(r"(?<!\\)\|", row.strip())) - 2
            for row in _TABLE_ROW.findall(_prose(text))
        ]

    assert shape(translated) == shape(english)
