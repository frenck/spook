"""Reading the corpus case files.

A case file is two YAML documents: what the case is about, then the
configuration itself. See the README next to this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterable

CORPUS = Path(__file__).parent

#: What a case may say about itself in its first document.
METADATA_KEYS = frozenset({"source", "note", "expect", "known_issue", "out_of_scope"})

#: What a rule under `expect` may hold, per reference type.
RULE_KEYS = frozenset({"find", "not_find"})


class CorpusLoader(yaml.SafeLoader):  # pylint: disable=too-many-ancestors
    """A safe loader that keeps Home Assistant's own tags as opaque strings.

    `!secret`, `!input`, `!include` and friends need a house, a blueprint or
    a directory to mean something, and a case has none of those. Read as
    `"!input motion_sensor"`, they make a case a parser fixture: it proves a
    reader does not trip over the text. It is not what Home Assistant hands
    the repairs, which see inputs filled in and files read.
    """


def _opaque_tag(loader: CorpusLoader, tag_suffix: str, node: yaml.Node) -> Any:
    """Return a tagged scalar as its tag and value, anything else untagged."""
    if isinstance(node, yaml.ScalarNode):
        return f"!{tag_suffix} {loader.construct_scalar(node)}".rstrip()
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_mapping(node, deep=True)  # type: ignore[arg-type]


CorpusLoader.add_multi_constructor("!", _opaque_tag)


@dataclass(frozen=True, slots=True)
class Case:
    """One case file, read."""

    path: Path
    kind: str
    metadata: dict[str, Any]
    config: Any

    @property
    def name(self) -> str:
        """Return how this case is called in test IDs and snapshots."""
        return self.path.stem

    @property
    def location(self) -> str:
        """Return where this case lives, for failure messages."""
        return str(self.path.relative_to(CORPUS.parent.parent))


def load_case(path: Path) -> Case:
    """Read a case file into its two documents.

    Raises `ValueError` when it does not hold exactly two documents, since
    anything else is a case nobody can read the same way twice.
    """
    with path.open(encoding="utf-8") as file:
        documents = list(yaml.load_all(file, Loader=CorpusLoader))

    if len(documents) != 2:  # noqa: PLR2004
        message = (
            f"{path} holds {len(documents)} YAML documents, expected two: "
            "the metadata, then the configuration"
        )
        raise ValueError(message)

    metadata, config = documents
    return Case(
        path=path,
        kind=path.parent.name,
        metadata=metadata if isinstance(metadata, dict) else {},
        config=config,
    )


def case_paths(kind: str) -> list[Path]:
    """Return the case files of one kind, in a stable order."""
    return sorted((CORPUS / kind).glob("*.yaml"))


def all_case_paths(kinds: Iterable[str]) -> list[Path]:
    """Return the case files of every kind, in a stable order."""
    return [path for kind in kinds for path in case_paths(kind)]


def rule_entries(entries: Any) -> list[str]:
    """Return the entries of one `find` or `not_find` rule as plain strings.

    An attribute or a state is written as a mapping, `light.kitchen: "On"`,
    and compared as the line the harness reports, `light.kitchen: On`.
    """
    if not isinstance(entries, list):
        entries = [entries]

    found: list[str] = []
    for entry in entries:
        if isinstance(entry, dict):
            found.extend(f"{key}: {value}" for key, value in entry.items())
        else:
            found.append(str(entry))
    return found
